"""发票核心：上传(S3+入队) / 列表 / 详情 / 校对保存(防重) / 报销流转 / 删除 / 60s 预览。"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import Date, case, cast, func, select
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
    BulkDeleteRequest,
    BulkResult,
    BulkStatusUpdate,
    DuplicateCheckIn,
    DuplicateCheckOut,
    ExportRequest,
    InvoiceOut,
    InvoiceUpdate,
    PreviewOut,
    ReimbursementStatusUpdate,
)
from app.services import email_parse
from app.services.export import build_export_zip
from app.services.ingest import detect_file_type, persist_invoice_bytes
from app.services.seller_category import upsert_rule

router = APIRouter(prefix="/invoices", tags=["invoices"])

MAX_FILE_SIZE = 15 * 1024 * 1024  # 单个 PDF/图片上限 15MB
MAX_ZIP_SIZE = 64 * 1024 * 1024  # 批量发票 ZIP 上限 64MB（如京东发票中心批量下载包）


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


async def _persist_invoice(
    session: AsyncSession, user: User, content: bytes, ext: str, ctype: str
) -> Invoice | None:
    """落库一张手动上传的发票（共享去重/上传/落库逻辑见 services.ingest）。"""
    return await persist_invoice_bytes(
        session, user.id, content, ext, ctype, InvoiceSource.MANUAL.value
    )


@router.post("/upload", response_model=list[InvoiceOut], status_code=status.HTTP_201_CREATED)
async def upload(
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Invoice]:
    created: list[Invoice] = []
    for f in files:
        content = await f.read()
        is_zip = content[:4] == b"PK\x03\x04"
        limit = MAX_ZIP_SIZE if is_zip else MAX_FILE_SIZE
        if len(content) > limit:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"文件过大（上限 {limit // (1024 * 1024)}MB）",
            )
        if is_zip:
            # ZIP（如京东发票中心批量下载包）：解出其中每张发票 PDF，各建一条记录。
            pdfs = email_parse.pdfs_from_zip_bytes(content)
            if not pdfs:
                raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "ZIP 中未找到发票 PDF")
            for pdf in pdfs:
                inv = await _persist_invoice(session, user, pdf, ".pdf", "application/pdf")
                if inv is not None:
                    created.append(inv)
        else:
            detected = detect_file_type(content)
            if detected is None:
                raise HTTPException(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "不支持的文件类型（需 PDF/PNG/JPG 或 ZIP）",
                )
            ext, ctype = detected
            inv = await _persist_invoice(session, user, content, ext, ctype)
            if inv is not None:
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
    # 默认排序：待报销的优先（用户最需处理的浮到最前），其次按时间最新在前。
    # 时间轴用开票日期，缺失（刚同步未抽取）时回退入库时间，保证单调“最新在前”；同日按入库时间兜底。
    status_priority = case(
        (Invoice.reimbursement_status == ReimbursementStatus.UNREIMBURSED.value, 0),
        (Invoice.reimbursement_status == ReimbursementStatus.SUBMITTED.value, 1),
        else_=2,
    )
    stmt = (
        select(Invoice)
        .where(Invoice.user_id == user.id)
        .order_by(
            status_priority,
            func.coalesce(Invoice.issue_date, cast(Invoice.created_at, Date)).desc(),
            Invoice.created_at.desc(),
        )
    )
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


@router.post("/export")
async def export_invoices(
    data: ExportRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    rows = list(
        await session.scalars(
            select(Invoice).where(Invoice.user_id == user.id, Invoice.id.in_(data.invoice_ids))
        )
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未找到要导出的发票")

    zip_bytes = await build_export_zip(rows, storage.download_bytes)

    # 导出即提交流转：勾选的待报销票批量原子化改为报销中
    if data.mark_submitted:
        for inv in rows:
            if inv.reimbursement_status == ReimbursementStatus.UNREIMBURSED.value:
                inv.reimbursement_status = ReimbursementStatus.SUBMITTED.value
        await session.commit()

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="reimbursement.zip"'},
    )


async def _owned_invoices(
    session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[Invoice]:
    """取当前用户名下、且 id 在给定集合内的发票（越权的 id 自然被过滤掉）。"""
    return list(
        await session.scalars(
            select(Invoice).where(Invoice.user_id == user_id, Invoice.id.in_(ids))
        )
    )


@router.post("/bulk/reimbursement-status", response_model=BulkResult)
async def bulk_update_reimbursement_status(
    data: BulkStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BulkResult:
    """批量改报销状态：把选中的(本人)发票一次性改为目标状态（任意方向）。"""
    if data.reimbursement_status not in _REIMBURSE_ORDER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "非法的报销状态")
    rows = await _owned_invoices(session, user.id, data.invoice_ids)
    for inv in rows:
        inv.reimbursement_status = data.reimbursement_status
    await session.commit()
    return BulkResult(count=len(rows))


@router.post("/bulk-delete", response_model=BulkResult)
async def bulk_delete_invoices(
    data: BulkDeleteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BulkResult:
    """批量删除：删除选中的(本人)发票及其原件（原件清理 best-effort）。"""
    rows = await _owned_invoices(session, user.id, data.invoice_ids)
    keys = [inv.file_key for inv in rows]
    for inv in rows:
        await session.delete(inv)
    await session.commit()
    for key in keys:
        await storage.delete_object(key)
    return BulkResult(count=len(rows))


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
    if data.reimbursement_status not in _REIMBURSE_ORDER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "非法的报销状态")
    # 自由改：允许任意方向（便于把误标的「已完成/报销中」改回纠错）。
    inv.reimbursement_status = data.reimbursement_status
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
    key = inv.file_key
    await session.delete(inv)
    await session.commit()
    await storage.delete_object(key)  # best-effort 清理原件，失败不影响删除


@router.get("/{invoice_id}/preview", response_model=PreviewOut)
async def preview(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PreviewOut:
    inv = await _get_owned(invoice_id, user, session)
    url = await storage.presigned_get_url(inv.file_key)
    return PreviewOut(url=url, expires_in=settings.presigned_expire_seconds)
