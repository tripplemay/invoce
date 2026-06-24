"""报销单异步导出任务：创建 / 列表 / 下载。"""

import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core import storage
from app.core.config import settings
from app.core.db import get_session
from app.core.queue import get_pool
from app.models.enums import EmailSendStatus, ExportTaskStatus
from app.models.export_email_send import ExportEmailSend
from app.models.export_task import ExportTask
from app.models.user import User
from app.schemas.export import ExportDownloadOut, ExportTaskCreate, ExportTaskOut
from app.schemas.export_send import ExportSendCreate, ExportSendOut
from app.services.export_runner import create_export_task
from app.services.export_sender import create_send_record

router = APIRouter(prefix="/export-tasks", tags=["export-tasks"])


async def _get_completed_owned_task(
    task_id: uuid.UUID, user: User, session: AsyncSession
) -> ExportTask:
    """取本人的、已完成且结果 key 合法的导出任务（下载/发送共用的校验）。"""
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
    return task


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
    task = await _get_completed_owned_task(task_id, user, session)
    # result_file_key 已由 _get_completed_owned_task 校验为合法非空 key
    url = await storage.presigned_get_url(
        cast(str, task.result_file_key), download_filename=task.result_filename
    )
    return ExportDownloadOut(url=url, expires_in=settings.presigned_expire_seconds)


@router.post("/{task_id}/send", response_model=ExportSendOut, status_code=status.HTTP_201_CREATED)
async def send_task(
    task_id: uuid.UUID,
    data: ExportSendCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExportEmailSend:
    """把已完成任务的报销单发到指定邮箱（通讯录 + / 或临时邮箱），worker 异步投递。"""
    if not settings.outbound_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "邮件发送暂未开启")
    task = await _get_completed_owned_task(task_id, user, session)
    record = await create_send_record(
        session, user.id, task, data.contact_ids, data.emails, data.note
    )
    if record is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有有效的收件人")
    try:
        pool = await get_pool()
        try:
            await pool.enqueue_job("send_export_email", str(record.id))
        finally:
            await pool.aclose()
    except Exception:  # noqa: BLE001 队列不可用时把记录标失败，避免永远卡在 pending
        record.status = EmailSendStatus.FAILED.value
        record.error_message = "任务队列暂不可用，请稍后重试"
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "任务队列暂不可用，请稍后重试"
        ) from None
    return record


@router.get("/{task_id}/sends", response_model=list[ExportSendOut])
async def list_sends(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ExportEmailSend]:
    """某个导出任务的发送记录，最新在前。"""
    task = await session.get(ExportTask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    rows = await session.scalars(
        select(ExportEmailSend)
        .where(ExportEmailSend.export_task_id == task_id)
        .order_by(ExportEmailSend.created_at.desc())
    )
    return list(rows)
