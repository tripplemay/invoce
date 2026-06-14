import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Invoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ---- AI 抽取字段：上传即建记录(processing)时尚无值，故可空；校对通过(verified)时应填全（应用层强约束）----
    invoice_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 全电发票为空
    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)), nullable=True)
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    # ---- 流转/系统字段：始终存在 ----
    reimbursement_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="unreimbursed"
    )
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="processing")

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','pending','verified','failed')", name="ck_invoice_status"
        ),
        CheckConstraint(
            "reimbursement_status IN ('unreimbursed','submitted','reimbursed')",
            name="ck_invoice_reimbursement_status",
        ),
        CheckConstraint("source IN ('manual','email_auto')", name="ck_invoice_source"),
        # 邮件归集的文件级去重数据库权威：仅对 email_auto 生效——同一用户同一文件(sha256)只允许一行。
        # 让 DB 成为去重终点，避免“回填 + 增量 cron”并发时 check-then-act 竞态产生重复发票行。
        # 手动上传(source=manual)不受此约束，保留用户重复上传同一文件的自由。
        Index(
            "uq_invoice_email_file",
            "user_id",
            "file_key",
            unique=True,
            postgresql_where=text("source = 'email_auto'"),
        ),
        # 防重唯一索引：仅当已抽取出号码时生效（排除 processing/failed 空号码行）；
        # NULLS NOT DISTINCT 让 (code=NULL, number) 也能正确判重 —— 修复全电发票去重漏洞。
        Index(
            "uq_invoice_dedup",
            "user_id",
            "invoice_code",
            "invoice_number",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("invoice_number IS NOT NULL"),
        ),
    )
