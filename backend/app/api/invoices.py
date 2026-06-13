"""发票核心：上传(S3+入队) / 列表 / 详情 / 校对保存(防重) / 报销流转 / 删除 / 60s 预览。"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core import storage
from app.core.config import settings
from app.core.db import get_session
from app.core.queue import get_pool
from app.models.enums import InvoiceSource, InvoiceStatus, ReimbursementStatus
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.invoice import (
    DuplicateCheckIn,
    DuplicateCheckOut,
    InvoiceOut,
    InvoiceUpdate,
    PreviewOut,
    ReimbursementStatusUpdate,
)
from app.services.seller_category import upsert_rule

router = APIRouter(prefix="/invoices", tags=["invoices"])

# content_type -> 扩展名
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

_REIMBURSE_ORDER = {
    ReimbursementStatus.UNREIMBURSED.value: 0,
    ReimbursementStatus.SUBMITTED.value: 1,
    ReimbursementStatus.REIMBURSED.value: 2,
}


async def enqueue_extract(invoice_id: str) -> None:
    """投递 AI 抽取任务（阶段4 由 worker 消费）。"""
    pool = await get_pool()
    try:
        await pool.enqueue_job("extract_invoice", invoice_id)
    finally:
        await pool.aclose()


async def _get_owned(invoice_id: uuid.UUID, user: User, session: AsyncSession) -> Invoice:
    inv = await session.get(Invoice, invoice_id)
    if inv is None or inv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "发票不存在")
    return inv


async def _find_duplicate(
    session: AsyncSession,
    user_id: uuid.UUID,
    code: str | None,
    number: str | None,
    exclude_id: uuid.UUID | None = None,
) -> Invoice | None:
    """联合唯一检索：(user_id, invoice_code, invoice_number)，code 为 NULL 时按 NULL 相等处理。"""
    if not number:
        return None
    stmt = select(Invoice).where(Invoice.user_id == user_id, Invoice.invoice_number == number)
    stmt = stmt.where(
        Invoice.invoice_code.is_(None) if code is None else Invoice.invoice_code == code
    )
    if exclude_id is not None:
        stmt = stmt.where(Invoice.id != exclude_id)
    return await session.scalar(stmt)


@router.post("/upload", response_model=list[InvoiceOut], status_code=status.HTTP_201_CREATED)
async def upload(
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Invoice]:
    created: list[Invoice] = []
    for f in files:
        ext = ALLOWED_TYPES.get(f.content_type or "")
        if ext is None:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"不支持的文件类型: {f.content_type}"
            )
        content = await f.read()
        key = storage.build_key(str(user.id), content, ext)
        await storage.upload_bytes(key, content, f.content_type or "application/octet-stream")
        inv = Invoice(
            user_id=user.id,
            file_key=key,
            source=InvoiceSource.MANUAL.value,
            status=InvoiceStatus.PROCESSING.value,
            reimbursement_status=ReimbursementStatus.UNREIMBURSED.value,
        )
        session.add(inv)
        await session.flush()
        created.append(inv)
    await session.commit()
    for inv in created:
        await session.refresh(inv)
        await enqueue_extract(str(inv.id))
    return created


@router.get("", response_model=list[InvoiceOut])
async def list_invoices(
    reimbursement_status: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.user_id == user.id).order_by(Invoice.created_at.desc())
    if reimbursement_status:
        stmt = stmt.where(Invoice.reimbursement_status == reimbursement_status)
    rows = await session.scalars(stmt)
    return list(rows)


@router.post("/check-duplicate", response_model=DuplicateCheckOut)
async def check_duplicate(
    data: DuplicateCheckIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DuplicateCheckOut:
    dup = await _find_duplicate(
        session, user.id, data.invoice_code, data.invoice_number, data.exclude_id
    )
    if dup is not None:
        return DuplicateCheckOut(
            duplicate=True,
            existing_id=dup.id,
            existing_date=dup.issue_date or dup.created_at.date(),
        )
    return DuplicateCheckOut(duplicate=False)


@router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Invoice:
    return await _get_owned(invoice_id, user, session)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
async def update_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Invoice:
    inv = await _get_owned(invoice_id, user, session)
    payload = data.model_dump(exclude_unset=True)
    new_code = payload.get("invoice_code", inv.invoice_code)
    new_number = payload.get("invoice_number", inv.invoice_number)

    dup = await _find_duplicate(session, user.id, new_code, new_number, exclude_id=inv.id)
    if dup is not None:
        existing_date = dup.issue_date or dup.created_at.date()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"该发票已于 {existing_date} 录入系统，存在重复报销风险！",
        )

    for key, value in payload.items():
        setattr(inv, key, value)
    # 校对保存：号码齐全则标记已校对
    if inv.invoice_number:
        inv.status = InvoiceStatus.VERIFIED.value
    # 学习开票方→分类映射（用户纠正分类后记忆，后续同开票方自动套用）
    if inv.category and inv.seller_name:
        await upsert_rule(session, user.id, inv.seller_name, inv.category)
    await session.commit()
    await session.refresh(inv)
    return inv


@router.patch("/{invoice_id}/reimbursement-status", response_model=InvoiceOut)
async def update_reimbursement_status(
    invoice_id: uuid.UUID,
    data: ReimbursementStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Invoice:
    inv = await _get_owned(invoice_id, user, session)
    target = data.reimbursement_status
    if target not in _REIMBURSE_ORDER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "非法的报销状态")
    if _REIMBURSE_ORDER[target] <= _REIMBURSE_ORDER[inv.reimbursement_status]:
        raise HTTPException(status.HTTP_409_CONFLICT, "报销状态只能向前流转，不可回退")
    inv.reimbursement_status = target
    await session.commit()
    await session.refresh(inv)
    return inv


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    inv = await _get_owned(invoice_id, user, session)
    await session.delete(inv)
    await session.commit()


@router.get("/{invoice_id}/preview", response_model=PreviewOut)
async def preview(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PreviewOut:
    inv = await _get_owned(invoice_id, user, session)
    url = await storage.presigned_get_url(inv.file_key)
    return PreviewOut(url=url, expires_in=settings.presigned_expire_seconds)
