"""export_email_sends 表：报销单一键发送记录

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_email_sends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "export_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("export_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("to_addresses", postgresql.JSONB(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("delivery_mode", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending','sending','sent','failed')",
            name="ck_export_email_send_status",
        ),
    )
    op.create_index("ix_export_email_sends_user_id", "export_email_sends", ["user_id"])
    op.create_index(
        "ix_export_email_sends_export_task_id", "export_email_sends", ["export_task_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_export_email_sends_export_task_id", table_name="export_email_sends")
    op.drop_index("ix_export_email_sends_user_id", table_name="export_email_sends")
    op.drop_table("export_email_sends")
