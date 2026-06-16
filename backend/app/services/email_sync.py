"""QQ 邮箱 IMAP 自动归集：搜索发票邮件(读+未读) → 提取 PDF/图 → 存 S3 + 建记录 + 入队。

幂等三层：
- 增量靠 email_accounts.last_sync_uid（UID 递增水位线，只取其上、升序成批推进，保证连续不漏不重）；
- 文件级靠 file_key=sha256（同一文件已入库则跳过，回填/重跑不产生重复发票行）；
- fetch 用 BODY.PEEK，不改邮件已读状态。

中国电子发票/行程单的邮件主题几乎都含“发票”或“行程单”，故按主题中文关键词在服务端搜索。
注意：QQ IMAP 对“多关键词 + 中文 + charset”的组合 OR 搜索会把中文项整体丢弃（实测只剩 ASCII 项生效），
因此必须对每个关键词单独 SUBJECT 搜索，再在客户端取并集去重。
"""

import email
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.models.email_account import EmailAccount
from app.models.email_sync_log import EmailSyncLog
from app.models.enums import EmailSyncStatus, InvoiceSource
from app.services import email_parse, link_fetch
from app.services.ingest import persist_invoice_bytes

Enqueue = Callable[[str], Awaitable[None]]
Fetcher = Callable[[EmailAccount], Awaitable[list[tuple[int, bytes]]]]

# 服务端按主题中文关键词搜索（逐词单独搜，客户端并集）。仅归集标准中国发票：
# 只搜“发票”——行程单/账单等不是标准发票，不搜（同邮件里夹带的也按文件名在 ingest 处剔除）。
_SUBJECT_KEYWORDS = ("发票",)
# 单次增量处理的最大封数：取水位线之上“最低”一批（升序），使水位连续推进，余量留给下次。
MAX_PER_SYNC = 100
# 小于此字节数的图片视为 logo / 跟踪像素，丢弃；PDF 不受限。
MIN_IMAGE_BYTES = 8000


async def ingest_raw_email(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_bytes: bytes,
    enqueue: Enqueue,
    *,
    source: str,
    link_fetcher: link_fetch.LinkFetcher = link_fetch.fetch_invoice_pdfs,
) -> tuple[str, int]:
    """解析单封原始邮件 → 入库到 user_id 名下，返回 (状态, 新增发票数)。写 email_sync_logs。

    IMAP 归集与「专属收票邮箱」入站共用此核心（各传自己的 user_id 与 source）。
    """
    msg = email.message_from_bytes(raw_bytes)
    subject = email_parse.decode_mime_header(msg.get("Subject"))
    sender = email_parse.decode_mime_header(msg.get("From"))
    body = email_parse.body_text(msg)

    keyword_ok = email_parse.matches_keywords(subject, body)
    # IMAP 要扫整个收件箱：靠主题/正文关键词预筛，避免误收非发票邮件。
    # 专属收票邮箱是用户主动投递、意图明确：不做关键词预筛——只要带 PDF/图附件或发票直链就收
    # （哪怕主题是 "test"）。营销/钓鱼风险靠下游的附件类型 + 图片大小 + 噪音文件名过滤兜底。
    if source != InvoiceSource.EMAIL_INBOUND.value and not keyword_ok:
        session.add(
            EmailSyncLog(
                user_id=user_id,
                sender=sender,
                subject=subject,
                status=EmailSyncStatus.IGNORED.value,
                invoice_count=0,
            )
        )
        await session.commit()
        return (EmailSyncStatus.IGNORED.value, 0)

    # 取标准发票文件，按权威性优先级：
    # 1) 松散 PDF/图附件（已剔噪音）+ zip 内发票 PDF（含一封多张）；
    # 2) 无附件时，抽正文白名单内的免登录发票直链并拉取 PDF（如京东 jdcloud-oss 预签名直链）；
    # 3) 仍无则回退 HTML 内嵌 base64 图。
    # 不再无差别下载正文外链：仅按域名白名单拉取发票直链，避免营销/跟踪图与 SSRF/钓鱼风险面。
    files = email_parse.extract_attachments(msg)
    files += email_parse.extract_zip_pdfs(msg)
    link_fetch_pending = False  # 有发票直链却一张都没拉到 → 别静默成 SUCCESS/0，留可查诊断
    if not files:
        htmls = email_parse.html_parts(msg)
        links: list[str] = []
        for html in htmls:
            links += link_fetch.extract_invoice_pdf_links(html)
        if links:
            files += [(pdf, "application/pdf") for pdf in await link_fetcher(links)]
            link_fetch_pending = not files
        # 正文内嵌 base64 图最易误收营销图/签名图：仅在关键词命中时才回退抽取
        # （IMAP 走到这里必然已命中；inbound 主题无关键词时不冒这个险）。
        if not files and keyword_ok:
            for html in htmls:
                files += email_parse.extract_inline_base64_images(html)
    # 丢弃过小图片（签名 logo / 跟踪像素）；PDF 始终保留。
    files = [(c, t) for (c, t) in files if t == "application/pdf" or len(c) >= MIN_IMAGE_BYTES]

    created_ids: list[str] = []
    for content, ctype in files:
        ext = email_parse.ALLOWED_TYPES.get(ctype, ".jpg")
        inv = await persist_invoice_bytes(session, user_id, content, ext, ctype, source)
        if inv is not None:
            created_ids.append(str(inv.id))

    note: str | None = None
    if link_fetch_pending and not created_ids:
        note = "检测到链接式发票直链但未拉到 PDF，待回填重试"
    elif source == InvoiceSource.EMAIL_INBOUND.value and not created_ids:
        # 收票邮箱专属诊断：收到邮件却 0 入库时，把原因写进日志（去重 / 噪音 / 非PDF / 无附件）
        if files:
            note = f"收到 {len(files)} 个发票文件，但与库中已有发票重复（去重），未新增"
        else:
            desc = email_parse.describe_candidate_files(msg)
            note = "未发现可识别发票文件（PDF/图片附件）" + (
                "；附件诊断: " + " | ".join(desc) if desc else "；邮件无附件"
            )
    session.add(
        EmailSyncLog(
            user_id=user_id,
            sender=sender,
            subject=subject,
            status=EmailSyncStatus.SUCCESS.value,
            invoice_count=len(created_ids),
            error_message=note,
        )
    )
    await session.commit()
    for iid in created_ids:
        await enqueue(iid)
    return (EmailSyncStatus.SUCCESS.value, len(created_ids))


async def ingest_email(
    session: AsyncSession,
    account: EmailAccount,
    raw_bytes: bytes,
    enqueue: Enqueue,
    *,
    link_fetcher: link_fetch.LinkFetcher = link_fetch.fetch_invoice_pdfs,
) -> tuple[str, int]:
    """IMAP 归集单封邮件（薄封装，沿用 EMAIL_AUTO 来源）。"""
    return await ingest_raw_email(
        session,
        account.user_id,
        raw_bytes,
        enqueue,
        source=InvoiceSource.EMAIL_AUTO.value,
        link_fetcher=link_fetcher,
    )


def _extract_raw(resp) -> bytes:  # pragma: no cover - 依赖真实 IMAP 响应结构
    for line in getattr(resp, "lines", []) or []:
        if isinstance(line, (bytes, bytearray)) and len(line) > 100:
            return bytes(line)
    return b""


def _parse_uid_line(resp) -> list[int]:  # pragma: no cover
    if resp.result != "OK" or not resp.lines or not resp.lines[0]:
        return []
    line = resp.lines[0]
    if isinstance(line, (bytes, bytearray)):
        line = line.decode(errors="ignore")
    return [int(x) for x in line.split() if x.isdigit()]


async def _connect(account: EmailAccount):  # pragma: no cover
    import aioimaplib

    client = aioimaplib.IMAP4_SSL(host=account.imap_host, port=account.imap_port, timeout=30)
    await client.wait_hello_from_server()
    await client.login(account.imap_user, decrypt(account.auth_code_enc))
    return client


async def _search_uids(client, *extra: str) -> list[int]:  # pragma: no cover
    """对每个中文主题关键词单独服务端搜索，客户端并集去重（读+未读）。
    extra 为附加 AND 条件（如 "SINCE", "01-Jan-2026"）。"""
    found: set[int] = set()
    for kw in _SUBJECT_KEYWORDS:
        resp = await client.uid_search(*extra, "SUBJECT", kw, charset="UTF-8")
        found.update(_parse_uid_line(resp))
    return sorted(found)


async def _fetch_raw(client, uid: int) -> bytes:  # pragma: no cover
    fr = await client.uid("fetch", str(uid), "(BODY.PEEK[])")
    return _extract_raw(fr)


async def fetch_new_messages(account: EmailAccount) -> list[tuple[int, bytes]]:  # pragma: no cover
    """增量：取 UID > 水位线 的发票邮件，升序取最低一批（最多 MAX_PER_SYNC）。"""
    client = await _connect(account)
    try:
        await client.select("INBOX")
        last = account.last_sync_uid or 0
        batch = [u for u in await _search_uids(client) if u > last][:MAX_PER_SYNC]
        # 即便 fetch 失败(raw 为空)也带回该 UID：交给 sync_account 当作失败处理、不让水位线越过它，
        # 避免取信瞬时失败（超时/分块响应）导致中间某封发票被永久跳过。
        out: list[tuple[int, bytes]] = []
        for uid in batch:
            out.append((uid, await _fetch_raw(client, uid)))
        return out
    finally:
        await client.logout()


async def sync_account(
    session: AsyncSession,
    account: EmailAccount,
    enqueue: Enqueue,
    fetcher: Fetcher = fetch_new_messages,
) -> int:
    """同步单个邮箱，返回新增发票数。

    水位线只推进到“首个失败之前的连续成功 UID”：任何取信失败(raw 为空)或解析失败的邮件都不被越过，
    留待下轮重试——保证发票绝不被永久跳过。依赖批次按 UID 升序；失败之后已成功入库的更高 UID 邮件，
    下轮被重新处理时靠 file_key 唯一约束去重，不会重复入库。"""
    user_id = account.user_id  # 提前捕获，避免 rollback 后访问过期 ORM 属性
    messages = await fetcher(account)
    total = 0
    watermark = account.last_sync_uid or 0
    blocked = False  # 一旦遇到失败，水位线不再越过该 UID 及其后的任何 UID
    for uid, raw in messages:
        if not raw:  # 取信失败：阻止水位线越过，下轮重试
            blocked = True
            session.add(
                EmailSyncLog(
                    user_id=user_id,
                    sender="",
                    subject="(取信失败)",
                    status=EmailSyncStatus.FAILED.value,
                    error_message=f"fetch uid={uid} 返回空",
                )
            )
            await session.commit()
            continue
        try:
            _, count = await ingest_email(session, account, raw, enqueue)
            total += count
            if not blocked:
                watermark = uid
        except Exception as exc:  # noqa: BLE001 单封失败不阻断后续，但阻止水位线越过
            blocked = True
            await session.rollback()
            session.add(
                EmailSyncLog(
                    user_id=user_id,
                    sender="",
                    subject="(解析失败)",
                    status=EmailSyncStatus.FAILED.value,
                    error_message=str(exc)[:500],
                )
            )
            await session.commit()
    if watermark > (account.last_sync_uid or 0):
        account.last_sync_uid = watermark
        await session.commit()
    return total


async def backfill_account(
    session: AsyncSession, account: EmailAccount, enqueue: Enqueue, since: str
) -> int:  # pragma: no cover - 一次性运维任务，依赖真实 IMAP
    """一次性回填：取主题含发票/行程单、SINCE 指定日期(如 "01-Jan-2026")的邮件（读+未读），
    逐封 ingest（靠 file_key 去重）。不依赖水位线；结束后把水位线设为“本次回填处理过的发票 UID 的最大值”
    （不是信箱 ALL 的最大值，否则回填运行期间新到达的发票会被顶到水位线之上而被增量永久跳过）。
    增量随后会重扫该区间，file_key 唯一约束保证重叠幂等。"""
    user_id = account.user_id
    client = await _connect(account)
    total = 0
    try:
        await client.select("INBOX")
        invoice_uids = await _search_uids(client, "SINCE", since)
        for uid in invoice_uids:
            try:
                raw = await _fetch_raw(client, uid)
                if not raw:
                    continue
                _, count = await ingest_email(session, account, raw, enqueue)
                total += count
            except Exception as exc:  # noqa: BLE001 单封失败不阻断后续
                await session.rollback()
                session.add(
                    EmailSyncLog(
                        user_id=user_id,
                        sender="",
                        subject="(回填失败)",
                        status=EmailSyncStatus.FAILED.value,
                        error_message=str(exc)[:500],
                    )
                )
                await session.commit()
        if invoice_uids:
            account.last_sync_uid = max(max(invoice_uids), account.last_sync_uid or 0)
            await session.commit()
    finally:
        await client.logout()
    return total


async def sync_all(ctx: dict) -> str:
    """ARQ cron 入口：遍历所有启用的邮箱账户。"""
    maker = ctx["sessionmaker"]

    async def enqueue(invoice_id: str) -> None:
        await ctx["redis"].enqueue_job("extract_invoice", invoice_id)

    async with maker() as session:
        accounts = (
            await session.scalars(select(EmailAccount).where(EmailAccount.enabled.is_(True)))
        ).all()
        for account in accounts:
            account_user_id = account.user_id  # 提前捕获，避免 rollback 后属性过期
            try:
                await sync_account(session, account, enqueue)
            except Exception as exc:  # noqa: BLE001 连接失败记录日志，继续下一个
                await session.rollback()
                session.add(
                    EmailSyncLog(
                        user_id=account_user_id,
                        sender="",
                        subject="(连接失败)",
                        status=EmailSyncStatus.FAILED.value,
                        error_message=str(exc)[:500],
                    )
                )
                await session.commit()
    return "ok"
