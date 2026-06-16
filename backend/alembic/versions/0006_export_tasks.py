"""export_tasks 表：报销单异步导出任务

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("invoice_ids", postgresql.JSONB(), nullable=False),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mark_submitted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result_file_key", sa.String(length=512), nullable=True),
        sa.Column("result_filename", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending','processing','completed','failed')",
            name="ck_export_task_status",
        ),
    )
    op.create_index("ix_export_tasks_user_id", "export_tasks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_export_tasks_user_id", table_name="export_tasks")
    op.drop_table("export_tasks")
