"""报销单异步导出任务：创建 / 列表 / 下载。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core import storage
from app.core.config import settings
from app.core.db import get_session
from app.core.queue import get_pool
from app.models.enums import ExportTaskStatus
from app.models.export_task import ExportTask
from app.models.user import User
from app.schemas.export import ExportDownloadOut, ExportTaskCreate, ExportTaskOut
from app.services.export_runner import create_export_task

router = APIRouter(prefix="/export-tasks", tags=["export-tasks"])


@router.post("", response_model=ExportTaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: ExportTaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExportTask:
    """创建导出任务（立即返回），worker 异步打包；可选立即标记选中票为报销中。"""
    task = await create_export_task(session, user.id, data.invoice_ids, data.mark_submitted)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未找到要导出的发票")
    try:
        pool = await get_pool()
        try:
            await pool.enqueue_job("run_export", str(task.id))
        finally:
            await pool.aclose()
    except Exception:  # noqa: BLE001 队列不可用时把任务标失败，避免永远卡在 pending
        task.status = ExportTaskStatus.FAILED.value
        task.error_message = "任务队列暂不可用，请稍后重试"
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "任务队列暂不可用，请稍后重试"
        ) from None
    return task


@router.get("", response_model=list[ExportTaskOut])
async def list_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ExportTask]:
    """当前用户的导出任务，最新在前。"""
    rows = await session.scalars(
        select(ExportTask)
        .where(ExportTask.user_id == user.id)
        .order_by(ExportTask.created_at.desc())
    )
    return list(rows)


@router.get("/{task_id}/download", response_model=ExportDownloadOut)
async def download_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExportDownloadOut:
    """完成的任务返回短时效预签名下载链接（直连 R2，附件下载）。"""
    task = await session.get(ExportTask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    # 结果 key 必须落在本人导出前缀下，纵深防御（key 本由服务端写入）
    expected_prefix = f"{task.user_id}/exports/"
    if (
        task.status != ExportTaskStatus.COMPLETED.value
        or not task.result_file_key
        or not task.result_file_key.startswith(expected_prefix)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "任务尚未完成")
    url = await storage.presigned_get_url(
        task.result_file_key, download_filename=task.result_filename
    )
    return ExportDownloadOut(url=url, expires_in=settings.presigned_expire_seconds)
