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
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.crypto import decrypt
from app.models.email_account import EmailAccount
from app.models.email_sync_log import EmailSyncLog
from app.models.enums import EmailSyncStatus, InvoiceSource, InvoiceStatus, ReimbursementStatus
from app.models.invoice import Invoice
from app.services import email_parse

Enqueue = Callable[[str], Awaitable[None]]
Fetcher = Callable[[EmailAccount], Awaitable[list[tuple[int, bytes]]]]

# 服务端按主题中文关键词搜索（逐词单独搜，客户端并集）。仅中国发票：不含英文 Invoice。
_SUBJECT_KEYWORDS = ("发票", "行程单")
# 单次增量处理的最大封数：取水位线之上“最低”一批（升序），使水位连续推进，余量留给下次。
MAX_PER_SYNC = 100
# 小于此字节数的图片视为 logo / 跟踪像素，丢弃；PDF 不受限。
MIN_IMAGE_BYTES = 8000


async def ingest_email(
    session: AsyncSession, account: EmailAccount, raw_bytes: bytes, enqueue: Enqueue
) -> tuple[str, int]:
    """处理单封邮件：返回 (状态, 新增发票数)。写 email_sync_logs 但不更新 last_sync_uid。"""
    msg = email.message_from_bytes(raw_bytes)
    subject = email_parse.decode_mime_header(msg.get("Subject"))
    sender = email_parse.decode_mime_header(msg.get("From"))
    body = email_parse.body_text(msg)

    if not email_parse.matches_keywords(subject, body):
        session.add(
            EmailSyncLog(
                user_id=account.user_id,
                sender=sender,
                subject=subject,
                status=EmailSyncStatus.IGNORED.value,
                invoice_count=0,
            )
        )
        await session.commit()
        return (EmailSyncStatus.IGNORED.value, 0)

    # 优先取附件（中国电子发票几乎都是 PDF 附件）；无附件再回退到 HTML 内嵌 base64 图。
    # 不再下载外链图：外链图基本是营销/跟踪图，既是噪音也是 SSRF 风险面。
    files = email_parse.extract_attachments(msg)
    if not files:
        for html in email_parse.html_parts(msg):
            files += email_parse.extract_inline_base64_images(html)
    # 丢弃过小图片（签名 logo / 跟踪像素）；PDF 始终保留。
    files = [(c, t) for (c, t) in files if t == "application/pdf" or len(c) >= MIN_IMAGE_BYTES]

    created_ids: list[str] = []
    for content, ctype in files:
        ext = email_parse.ALLOWED_TYPES.get(ctype, ".jpg")
        key = storage.build_key(str(account.user_id), content, ext)
        # 幂等快路径：同一文件已入库则跳过，避免回填/重跑产生重复发票行。
        dup = await session.scalar(
            select(Invoice.id).where(Invoice.user_id == account.user_id, Invoice.file_key == key)
        )
        if dup:
            continue
        await storage.upload_bytes(key, content, ctype)
        inv = Invoice(
            user_id=account.user_id,
            file_key=key,
            source=InvoiceSource.EMAIL_AUTO.value,
            status=InvoiceStatus.PROCESSING.value,
            reimbursement_status=ReimbursementStatus.UNREIMBURSED.value,
        )
        # 幂等兜底：唯一约束 (user_id, file_key) 是去重终点。回填+增量并发时快路径可能漏判，
        # 用 SAVEPOINT 隔离单文件插入，撞唯一约束即视为已存在、跳过且不入队，不连累同邮件其它附件。
        try:
            async with session.begin_nested():
                session.add(inv)
                await session.flush()
        except IntegrityError:
            continue
        created_ids.append(str(inv.id))

    session.add(
        EmailSyncLog(
            user_id=account.user_id,
            sender=sender,
            subject=subject,
            status=EmailSyncStatus.SUCCESS.value,
            invoice_count=len(created_ids),
        )
    )
    await session.commit()
    for iid in created_ids:
        await enqueue(iid)
    return (EmailSyncStatus.SUCCESS.value, len(created_ids))


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
