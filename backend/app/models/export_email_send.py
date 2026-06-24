"""报销单邮件发送记录：一次「发送到指定邮箱」= 一条记录，worker 异步投递后回填状态。"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class ExportEmailSend(UUIDPKMixin, TimestampMixin, Base):
    """把某个已完成导出任务的报销单发到一组邮箱的一次发送记录。"""

    __tablename__ = "export_email_sends"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    export_task_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("export_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 收件人邮箱（字符串数组，已解析联系人 + 临时邮箱、去重）。
    to_addresses: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 投递形态（发送时按 ZIP 大小回填）：attachment / link。
    delivery_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','sending','sent','failed')",
            name="ck_export_email_send_status",
        ),
    )
