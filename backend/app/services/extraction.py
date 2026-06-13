"""发票 AI 抽取主流程：下载原件 → (PDF 渲染) → 网关多模态抽取 → 套用分类规则 → 落库。"""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ai, storage
from app.core.pdf import pdf_first_page_png
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.services.seller_category import get_rule


def _parse_date(v: object) -> date | None:
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(v: object) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _image_for(file_key: str, raw: bytes) -> tuple[bytes, str]:
    key = file_key.lower()
    if key.endswith(".pdf"):
        return pdf_first_page_png(raw), "image/png"
    if key.endswith(".png"):
        return raw, "image/png"
    return raw, "image/jpeg"


async def run_extraction(session: AsyncSession, invoice_id: str | uuid.UUID) -> None:
    iid = uuid.UUID(invoice_id) if isinstance(invoice_id, str) else invoice_id
    inv = await session.get(Invoice, iid)
    if inv is None:
        return
    try:
        raw = await storage.download_bytes(inv.file_key)
        image, ctype = _image_for(inv.file_key, raw)
        fields = await ai.extract_invoice_fields(image, ctype)

        seller = fields.get("seller_name") or None
        category = fields.get("category") or None
        if seller:
            rule = await get_rule(session, inv.user_id, seller)
            if rule is not None:
                category = rule.category

        inv.invoice_code = fields.get("invoice_code") or None
        inv.invoice_number = fields.get("invoice_number") or None
        inv.issue_date = _parse_date(fields.get("issue_date"))
        inv.invoice_type = fields.get("invoice_type") or None
        inv.seller_name = seller
        inv.buyer_name = fields.get("buyer_name") or None
        inv.total_amount = _parse_decimal(fields.get("total_amount"))
        inv.category = category
        inv.ai_confidence = _parse_decimal(fields.get("confidence"))
        inv.status = InvoiceStatus.PENDING.value
        await session.commit()
    except Exception:  # noqa: BLE001 抽取任何环节失败都标记 failed
        await session.rollback()
        failed = await session.get(Invoice, iid)
        if failed is not None:
            failed.status = InvoiceStatus.FAILED.value
            await session.commit()
