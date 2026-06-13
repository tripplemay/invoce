"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ---- email_accounts ----
    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("imap_user", sa.String(255), nullable=False),
        sa.Column("auth_code_enc", sa.LargeBinary(), nullable=False),
        sa.Column("imap_host", sa.String(255), server_default="imap.qq.com", nullable=False),
        sa.Column("imap_port", sa.Integer(), server_default="993", nullable=False),
        sa.Column("last_sync_uid", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])

    # ---- invoices ----
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invoice_code", sa.String(64), nullable=True),
        sa.Column("invoice_number", sa.String(64), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("invoice_type", sa.String(32), nullable=True),
        sa.Column("seller_name", sa.String(255), nullable=True),
        sa.Column("buyer_name", sa.String(255), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(64)), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "reimbursement_status", sa.String(32), server_default="unreimbursed", nullable=False
        ),
        sa.Column("file_key", sa.String(512), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="processing", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processing','pending','verified','failed')", name="ck_invoice_status"
        ),
        sa.CheckConstraint(
            "reimbursement_status IN ('unreimbursed','submitted','reimbursed')",
            name="ck_invoice_reimbursement_status",
        ),
        sa.CheckConstraint("source IN ('manual','email_auto')", name="ck_invoice_source"),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    # 防重唯一索引：仅当 invoice_number 非空时生效；NULLS NOT DISTINCT 修复全电发票(code=NULL)去重漏洞
    op.execute(
        "CREATE UNIQUE INDEX uq_invoice_dedup ON invoices "
        "(user_id, invoice_code, invoice_number) NULLS NOT DISTINCT "
        "WHERE invoice_number IS NOT NULL"
    )

    # ---- seller_category_rules ----
    op.create_table(
        "seller_category_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seller_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "seller_name", name="uq_seller_category_rule"),
    )
    op.create_index("ix_seller_category_rules_user_id", "seller_category_rules", ["user_id"])

    # ---- email_sync_logs ----
    op.create_table(
        "email_sync_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sync_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("invoice_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('SUCCESS','FAILED','IGNORED')", name="ck_email_sync_status"),
    )
    op.create_index("ix_email_sync_logs_user_id", "email_sync_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("email_sync_logs")
    op.drop_table("seller_category_rules")
    op.execute("DROP INDEX IF EXISTS uq_invoice_dedup")
    op.drop_table("invoices")
    op.drop_table("email_accounts")
    op.drop_table("users")
