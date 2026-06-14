"""invoice email_auto file_key unique per user (邮件归集文件级去重的数据库权威)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 仅对 email_auto 生效：同一用户同一文件(sha256 内容哈希)只允许一行，防止“回填 + 增量 cron”并发时
    # 应用层 check-then-act 漏判导致同一 PDF 重复入库。手动上传(source=manual)不受约束。
    op.create_index(
        "uq_invoice_email_file",
        "invoices",
        ["user_id", "file_key"],
        unique=True,
        postgresql_where=sa.text("source = 'email_auto'"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_invoice_email_file")
