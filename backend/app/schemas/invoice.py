"""发票相关 Pydantic 模型。"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_code: str | None
    invoice_number: str | None
    issue_date: date | None
    invoice_type: str | None
    seller_name: str | None
    buyer_name: str | None
    total_amount: Decimal | None
    category: str | None
    tags: list[str] | None
    reimbursement_status: str
    source: str
    status: str
    ai_confidence: Decimal | None
    created_at: datetime
    updated_at: datetime


class InvoiceUpdate(BaseModel):
    invoice_code: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    invoice_type: str | None = None
    seller_name: str | None = None
    buyer_name: str | None = None
    total_amount: Decimal | None = None
    category: str | None = None
    tags: list[str] | None = None


class DuplicateCheckIn(BaseModel):
    invoice_code: str | None = None
    invoice_number: str
    exclude_id: uuid.UUID | None = None


class DuplicateCheckOut(BaseModel):
    duplicate: bool
    existing_id: uuid.UUID | None = None
    existing_date: date | None = None


class ReimbursementStatusUpdate(BaseModel):
    reimbursement_status: str


class PreviewOut(BaseModel):
    url: str
    expires_in: int


class ExportRequest(BaseModel):
    invoice_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    mark_submitted: bool = True
