"""一次性 IMAP 诊断：定位中文发票为何没被同步。读取库里启用的邮箱账户，直连 QQ IMAP，
对比服务端 SEARCH 计数 vs 客户端解码主题的关键词命中，并打印最近邮件的真实主题/已读/UID。"""

import asyncio
import email
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.crypto import decrypt
from app.models.email_account import EmailAccount
from app.services import email_parse

# 客户端关键词（中文发票常见词 + 英文）
KW = [
    "发票",
    "电子发票",
    "行程单",
    "增值税",
    "普通发票",
    "专用发票",
    "invoice",
    "receipt",
    "billing",
]


def parse_uids(resp) -> list[int]:
    if resp.result != "OK" or not resp.lines or not resp.lines[0]:
        return []
    line = resp.lines[0]
    if isinstance(line, (bytes, bytearray)):
        line = line.decode(errors="ignore")
    return [int(x) for x in line.split() if x.isdigit()]


def kw_hit(subject: str) -> str | None:
    low = (subject or "").lower()
    for k in KW:
        if k.lower() in low:
            return k
    return None


async def main():
    eng = create_async_engine(settings.database_url)
    async with async_sessionmaker(eng, expire_on_commit=False)() as s:
        acct = (await s.scalars(select(EmailAccount).where(EmailAccount.enabled.is_(True)))).first()
        host, port, user = acct.imap_host, acct.imap_port, acct.imap_user
        pwd = decrypt(acct.auth_code_enc)
        last_uid = acct.last_sync_uid
    await eng.dispose()

    import aioimaplib

    c = aioimaplib.IMAP4_SSL(host=host, port=port, timeout=60)
    await c.wait_hello_from_server()
    await c.login(user, pwd)
    sel = await c.select("INBOX")

    exists = None
    for ln in sel.lines:
        t = ln.decode(errors="ignore") if isinstance(ln, (bytes, bytearray)) else str(ln)
        m = re.match(r"(\d+) EXISTS", t)
        if m:
            exists = int(m.group(1))
    print(f"INBOX EXISTS = {exists}   last_sync_uid = {last_uid}   imap_user = {user}")

    async def scount(label, *crit, charset="UTF-8"):
        try:
            r = await c.uid_search(*crit, charset=charset)
            u = parse_uids(r)
            print(f"  [{label}] result={r.result} -> {len(u)} 封  (max uid {max(u) if u else '-'})")
            return u
        except Exception as ex:  # noqa: BLE001
            print(f"  [{label}] 异常: {ex!r}")
            return []

    print("=== A. 服务端 SEARCH 计数对比 ===")
    await scount("ALL", "ALL")
    unseen = await scount("UNSEEN", "UNSEEN")
    await scount("SUBJECT 发票", "SUBJECT", "发票")
    await scount("UNSEEN SUBJECT 发票", "UNSEEN", "SUBJECT", "发票")
    await scount("SUBJECT 电子发票", "SUBJECT", "电子发票")
    await scount("SUBJECT Invoice", "SUBJECT", "Invoice")
    await scount("UNSEEN SUBJECT Invoice", "UNSEEN", "SUBJECT", "Invoice")
    await scount("TEXT 发票", "TEXT", "发票")
    await scount(
        "当前 _KEYWORD_SEARCH",
        "UNSEEN",
        "OR",
        "SUBJECT",
        "发票",
        "OR",
        "SUBJECT",
        "行程单",
        "SUBJECT",
        "Invoice",
    )
    # 不带 charset 的中文搜索（部分服务器只认裸字节）
    await scount("SUBJECT 发票 (no charset)", "SUBJECT", "发票", charset=None)

    print("\n=== B. 最近 60 封邮件真实主题（客户端解码） ===")
    start = max(1, (exists or 1) - 59)
    fr = await c.fetch(
        f"{start}:{exists}", "(UID FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])"
    )
    intro_re = re.compile(r"UID (\d+)")
    flags_re = re.compile(r"FLAGS \(([^)]*)\)")
    recents = []
    cur = {}
    for ln in fr.lines:
        if isinstance(ln, (bytes, bytearray)) and b"Subject:" in ln:
            msg = email.message_from_bytes(bytes(ln))
            cur["subject"] = email_parse.decode_mime_header(msg.get("Subject"))
            cur["from"] = email_parse.decode_mime_header(msg.get("From"))
            if "uid" in cur:
                recents.append(cur)
            cur = {}
        else:
            t = ln.decode(errors="ignore") if isinstance(ln, (bytes, bytearray)) else str(ln)
            mu = intro_re.search(t)
            if mu and "FETCH" in t:
                if cur.get("subject") is not None:
                    recents.append(cur)
                mf = flags_re.search(t)
                cur = {"uid": int(mu.group(1)), "flags": mf.group(1) if mf else ""}
    if cur.get("subject") is not None and "uid" in cur:
        recents.append(cur)

    recents.sort(key=lambda r: r.get("uid", 0), reverse=True)
    inv_recent = 0
    below_wm = 0
    unseen_inv_recent = 0
    for r in recents:
        seen = "\\Seen" in r.get("flags", "")
        hit = kw_hit(r.get("subject", ""))
        if hit:
            inv_recent += 1
            if not seen:
                unseen_inv_recent += 1
            if r.get("uid", 0) <= (last_uid or 0):
                below_wm += 1
        mark = "★发票" if hit else "      "
        wm = "↓水位下" if r.get("uid", 0) <= (last_uid or 0) else ""
        rd = "已读" if seen else "未读"
        subj = (r.get("subject") or "")[:46]
        frm = (r.get("from") or "")[:24]
        print(f"  uid={r.get('uid'):>6} {rd} {mark} {wm:<6} | {subj:<46} | {frm}")

    print("\n=== C. 结论数据 ===")
    print(f"  最近 60 封里，主题含发票关键词的: {inv_recent} 封（其中未读 {unseen_inv_recent} 封）")
    print(f"  其中 UID ≤ 水位线({last_uid}) 会被永久跳过的: {below_wm} 封")
    print(f"  全箱未读总数: {len(unseen)}")
    print(
        "  → 若 B 段能看到大量中文发票，而 A 段 'SUBJECT 发票' 计数却很小/为 0，"
        "即证明 QQ 服务端中文搜索不可靠，必须改为客户端过滤。"
    )

    await c.logout()


asyncio.run(main())
