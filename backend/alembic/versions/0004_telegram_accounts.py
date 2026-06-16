"""telegram_accounts 表 + invoices.source 放开到 'telegram'

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_accounts",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
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
    op.create_index("ix_telegram_accounts_chat_id", "telegram_accounts", ["chat_id"], unique=True)
    # invoices.source 放开到 telegram
    op.drop_constraint("ck_invoice_source", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoice_source", "invoices", "source IN ('manual','email_auto','telegram')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoice_source", "invoices", type_="check")
    op.create_check_constraint("ck_invoice_source", "invoices", "source IN ('manual','email_auto')")
    op.drop_index("ix_telegram_accounts_chat_id", table_name="telegram_accounts")
    op.drop_table("telegram_accounts")
