"""报销单异步导出任务：记录请求、状态与生成结果（R2 key）。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class ExportTask(UUIDPKMixin, TimestampMixin, Base):
    """一次导出请求 = 一条任务；worker 异步打包后回填结果 key。"""

    __tablename__ = "export_tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    # 请求导出的发票 id（字符串数组），worker 据此取本人发票打包。
    invoice_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    mark_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 生成结果（完成后回填）：R2 对象 key + 建议下载文件名。
    result_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="ck_export_task_status",
        ),
    )
