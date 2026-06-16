"""报销单异步导出：创建任务（含可选标记报销中）+ worker 端打包上传。"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.enums import ExportTaskStatus, ReimbursementStatus
from app.models.export_task import ExportTask
from app.models.invoice import Invoice
from app.services.export import build_export_zip

logger = logging.getLogger(__name__)

Uploader = Callable[[str, bytes, str], Awaitable[None]]


async def create_export_task(
    session: AsyncSession,
    user_id: uuid.UUID,
    invoice_ids: list[uuid.UUID],
    mark_submitted: bool,
) -> ExportTask | None:
    """创建一条 pending 导出任务（只纳入本人发票）；可选立即把待报销票标记为报销中。

    返回 None 表示给定 id 下没有任何本人发票（API 转 404）。
    """
    rows = list(
        await session.scalars(
            select(Invoice).where(Invoice.user_id == user_id, Invoice.id.in_(invoice_ids))
        )
    )
    if not rows:
        return None

    if mark_submitted:
        for inv in rows:
            if inv.reimbursement_status == ReimbursementStatus.UNREIMBURSED.value:
                inv.reimbursement_status = ReimbursementStatus.SUBMITTED.value

    task = ExportTask(
        user_id=user_id,
        status=ExportTaskStatus.PENDING.value,
        invoice_ids=[str(inv.id) for inv in rows],  # 仅本人发票，越权 id 自然被过滤
        invoice_count=len(rows),
        mark_submitted=mark_submitted,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


def _result_filename(task: ExportTask) -> str:
    day = task.created_at.date().isoformat() if task.created_at else ""
    return f"报销单_{task.invoice_count}张_{day}.zip"


async def run_export_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    *,
    file_loader: Callable[[str], Awaitable[bytes]] = storage.download_bytes,
    uploader: Uploader = storage.upload_bytes,
) -> None:
    """worker 任务体：取本人发票 → 打包 ZIP → 上传 R2 → 回填结果 key/文件名。

    失败时把任务置 failed 并记录原因，不抛出（worker 不重试整个打包）。
    """
    task = await session.get(ExportTask, task_id)
    # 不存在 / 已完成（重复入队或 ARQ 重试）→ 跳过，保证幂等
    if task is None or task.status == ExportTaskStatus.COMPLETED.value:
        return
    task.status = ExportTaskStatus.PROCESSING.value
    await session.commit()

    try:
        ids = [uuid.UUID(s) for s in task.invoice_ids]
        rows = list(
            await session.scalars(
                select(Invoice).where(Invoice.user_id == task.user_id, Invoice.id.in_(ids))
            )
        )
        zip_bytes = await build_export_zip(rows, file_loader)
        key = f"{task.user_id}/exports/{task.id}.zip"
        await uploader(key, zip_bytes, "application/zip")

        task.result_file_key = key
        task.result_filename = _result_filename(task)
        task.status = ExportTaskStatus.COMPLETED.value
        task.completed_at = datetime.now(UTC)
        await session.commit()
    except Exception:  # noqa: BLE001 任何打包/上传失败都收口为 failed 任务，便于前端展示
        # 完整异常只记服务端日志；写库的 error_message 用通用文案，避免泄露存储路径/桶名等内部细节
        logger.exception("导出任务 %s 打包失败", task_id)
        await session.rollback()
        failed = await session.get(ExportTask, task_id)
        if failed is not None:
            failed.status = ExportTaskStatus.FAILED.value
            failed.error_message = "打包失败，请稍后重试"
            failed.completed_at = datetime.now(UTC)
            await session.commit()
