"""users.inbox_token(专属收票邮箱 localpart) + invoices.source 放开到 'email_inbound'

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("inbox_token", sa.String(length=64), nullable=True))
    op.create_index("ix_users_inbox_token", "users", ["inbox_token"], unique=True)
    op.drop_constraint("ck_invoice_source", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoice_source",
        "invoices",
        "source IN ('manual','email_auto','telegram','email_inbound')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoice_source", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoice_source", "invoices", "source IN ('manual','email_auto','telegram')"
    )
    op.drop_index("ix_users_inbox_token", table_name="users")
    op.drop_column("users", "inbox_token")
