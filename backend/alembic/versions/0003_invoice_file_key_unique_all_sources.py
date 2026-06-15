"""invoice file_key unique across all sources (放宽: 含手动上传，去重终点覆盖 manual)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 由"仅 email_auto"的部分唯一索引，放宽为对所有来源(含 manual 上传)生效的全量唯一索引。
    op.execute("DROP INDEX IF EXISTS uq_invoice_email_file")
    op.create_index("uq_invoice_user_file", "invoices", ["user_id", "file_key"], unique=True)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_invoice_user_file")
    op.create_index(
        "uq_invoice_email_file",
        "invoices",
        ["user_id", "file_key"],
        unique=True,
        postgresql_where=sa.text("source = 'email_auto'"),
    )
