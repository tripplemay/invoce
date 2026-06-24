"""报销单一键发送：解析收件人 + 建发送记录 + worker 端投递（智能附件/链接）。"""

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mailer, storage
from app.core.config import settings
from app.models.contact import Contact
from app.models.enums import EmailDeliveryMode, EmailSendStatus
from app.models.export_email_send import ExportEmailSend
from app.models.export_task import ExportTask

logger = logging.getLogger(__name__)

Mailer = Callable[..., Awaitable[None]]
LinkBuilder = Callable[..., Awaitable[str]]


async def resolve_recipients(
    session: AsyncSession,
    user_id: uuid.UUID,
    contact_ids: Sequence[uuid.UUID],
    emails: Sequence[str],
) -> list[str]:
    """把联系人 id（仅本人）解析为邮箱，并入临时邮箱；按小写去重、保序。"""
    resolved: list[str] = []
    if contact_ids:
        rows = await session.scalars(
            select(Contact).where(Contact.user_id == user_id, Contact.id.in_(list(contact_ids)))
        )
        resolved.extend(c.email for c in rows)
    resolved.extend(str(e) for e in emails)

    seen: set[str] = set()
    out: list[str] = []
    for addr in resolved:
        cleaned = addr.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def _subject(task: ExportTask) -> str:
    return f"报销材料（{task.invoice_count}张发票）"


def _body(task: ExportTask, note: str | None, *, link: str | None) -> str:
    note_block = f"\n备注：{note}\n" if note else ""
    if link is None:
        intro = (
            f"附件是一份报销材料，包含对账单（Excel）与全部发票原件，共 {task.invoice_count} 张。\n"
            "请查收并按流程处理。"
        )
    else:
        days = max(1, settings.email_link_expire_seconds // 86400)
        intro = (
            f"一份报销材料已生成（对账单 Excel + 全部发票原件，共 {task.invoice_count} 张），"
            f"因文件较大未作为附件，请在 {days} 天内通过以下链接下载：\n\n{link}"
        )
    return f"您好，\n\n{intro}\n{note_block}\n— 本邮件由发票助手自动发送，请勿直接回复。"


async def create_send_record(
    session: AsyncSession,
    user_id: uuid.UUID,
    task: ExportTask,
    contact_ids: Sequence[uuid.UUID],
    emails: Sequence[str],
    note: str | None,
) -> ExportEmailSend | None:
    """创建一条 pending 发送记录（收件人为空 → 返回 None，API 转 400）。"""
    recipients = await resolve_recipients(session, user_id, contact_ids, emails)
    if not recipients:
        return None
    record = ExportEmailSend(
        user_id=user_id,
        export_task_id=task.id,
        to_addresses=recipients,
        subject=_subject(task),
        note=note,
        status=EmailSendStatus.PENDING.value,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def run_send_task(
    session: AsyncSession,
    send_id: uuid.UUID,
    *,
    file_loader: Callable[[str], Awaitable[bytes]] = storage.download_bytes,
    send_mail: Mailer = mailer.send_email,
    link_builder: LinkBuilder = storage.presigned_get_url,
) -> None:
    """worker 任务体：取导出 ZIP → 按大小选附件/链接 → 发邮件 → 回填状态。

    失败时把记录置 failed 并记录通用原因，不抛出（worker 不整体重试投递）。
    """
    record = await session.get(ExportEmailSend, send_id)
    # 不存在 / 已发送（重复入队或 ARQ 重试）→ 跳过，保证幂等
    if record is None or record.status == EmailSendStatus.SENT.value:
        return
    record.status = EmailSendStatus.SENDING.value
    await session.commit()

    try:
        task = await session.get(ExportTask, record.export_task_id)
        if task is None or not task.result_file_key:
            raise RuntimeError("导出结果不存在")
        zip_bytes = await file_loader(task.result_file_key)
        filename = task.result_filename or "报销单.zip"

        if len(zip_bytes) <= settings.email_attach_max_bytes:
            mode = EmailDeliveryMode.ATTACHMENT
            body = _body(task, record.note, link=None)
            attachments = [(filename, zip_bytes, "application/zip")]
        else:
            mode = EmailDeliveryMode.LINK
            url = await link_builder(
                task.result_file_key,
                expires=settings.email_link_expire_seconds,
                download_filename=filename,
            )
            body = _body(task, record.note, link=url)
            attachments = []

        await send_mail(
            to=record.to_addresses,
            subject=record.subject or _subject(task),
            body=body,
            attachments=attachments,
        )

        record.delivery_mode = mode.value
        record.status = EmailSendStatus.SENT.value
        record.sent_at = datetime.now(UTC)
        await session.commit()
    except Exception:  # noqa: BLE001 任何投递失败都收口为 failed，便于前端展示
        # 完整异常只记服务端日志；写库的 error_message 用通用文案，避免泄露 SMTP/存储等内部细节
        logger.exception("报销单发送 %s 失败", send_id)
        await session.rollback()
        failed = await session.get(ExportEmailSend, send_id)
        if failed is not None:
            failed.status = EmailSendStatus.FAILED.value
            failed.error_message = "发送失败，请稍后重试"
            await session.commit()
