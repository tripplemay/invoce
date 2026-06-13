"""QQ 邮箱 IMAP 自动归集：拉未读 → 关键词过滤 → 提取发票 → 存 S3 + 建记录 + 入队。

幂等：靠 email_accounts.last_sync_uid（UID 递增），且 fetch 用 BODY.PEEK 不改已读状态。
"""

import email
from collections.abc import Awaitable, Callable

import httpx
from sqlalchemy import select
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


async def _download_external(urls: list[str]) -> list[tuple[bytes, str]]:
    files: list[tuple[bytes, str]] = []
    if not urls:
        return files
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for url in urls[:10]:
            try:
                r = await client.get(url)
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype in email_parse.ALLOWED_TYPES and r.content:
                    files.append((r.content, "image/jpeg" if ctype == "image/jpg" else ctype))
            except Exception:  # noqa: BLE001 外链下载尽力而为
                continue
    return files


async def ingest_email(
    session: AsyncSession, account: EmailAccount, raw_bytes: bytes, enqueue: Enqueue
) -> tuple[str, int]:
    """处理单封邮件：返回 (状态, 提取发票数)。写 email_sync_logs 但不更新 last_sync_uid。"""
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

    files = email_parse.extract_attachments(msg)
    for html in email_parse.html_parts(msg):
        files += email_parse.extract_inline_base64_images(html)
        files += await _download_external(email_parse.extract_external_image_urls(html))

    created_ids: list[str] = []
    for content, ctype in files:
        ext = email_parse.ALLOWED_TYPES.get(ctype, ".jpg")
        key = storage.build_key(str(account.user_id), content, ext)
        await storage.upload_bytes(key, content, ctype)
        inv = Invoice(
            user_id=account.user_id,
            file_key=key,
            source=InvoiceSource.EMAIL_AUTO.value,
            status=InvoiceStatus.PROCESSING.value,
            reimbursement_status=ReimbursementStatus.UNREIMBURSED.value,
        )
        session.add(inv)
        await session.flush()
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


async def fetch_unseen_messages(
    account: EmailAccount,
) -> list[tuple[int, bytes]]:  # pragma: no cover
    import aioimaplib

    client = aioimaplib.IMAP4_SSL(host=account.imap_host, port=account.imap_port, timeout=30)
    await client.wait_hello_from_server()
    await client.login(account.imap_user, decrypt(account.auth_code_enc))
    try:
        await client.select("INBOX")
        last = account.last_sync_uid or 0
        criteria = "UNSEEN" if not last else f"UNSEEN UID {last + 1}:*"
        resp = await client.uid("search", criteria)
        uids: list[int] = []
        if resp.result == "OK" and resp.lines and resp.lines[0]:
            uids = [int(x) for x in resp.lines[0].split()]
        out: list[tuple[int, bytes]] = []
        for uid in uids:
            if uid <= last:
                continue
            fr = await client.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = _extract_raw(fr)
            if raw:
                out.append((uid, raw))
        return out
    finally:
        await client.logout()


async def sync_account(
    session: AsyncSession,
    account: EmailAccount,
    enqueue: Enqueue,
    fetcher: Fetcher = fetch_unseen_messages,
) -> int:
    """同步单个邮箱，返回新增发票数。更新 last_sync_uid。"""
    messages = await fetcher(account)
    total = 0
    max_uid = account.last_sync_uid or 0
    for uid, raw in messages:
        try:
            _, count = await ingest_email(session, account, raw, enqueue)
            total += count
        except Exception as exc:  # noqa: BLE001 单封失败不阻断后续
            await session.rollback()
            session.add(
                EmailSyncLog(
                    user_id=account.user_id,
                    sender="",
                    subject="(解析失败)",
                    status=EmailSyncStatus.FAILED.value,
                    error_message=str(exc)[:500],
                )
            )
            await session.commit()
        max_uid = max(max_uid, uid)
    if messages:
        account.last_sync_uid = max_uid
        await session.commit()
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
            try:
                await sync_account(session, account, enqueue)
            except Exception as exc:  # noqa: BLE001 连接失败记录日志，继续下一个
                await session.rollback()
                session.add(
                    EmailSyncLog(
                        user_id=account.user_id,
                        sender="",
                        subject="(连接失败)",
                        status=EmailSyncStatus.FAILED.value,
                        error_message=str(exc)[:500],
                    )
                )
                await session.commit()
    return "ok"
