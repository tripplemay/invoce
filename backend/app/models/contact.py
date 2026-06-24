"""通讯录：用户维护的下游处理人联系人，用于一键发送报销单。"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Contact(UUIDPKMixin, TimestampMixin, Base):
    """一个收件联系人（按用户隔离，同一用户内邮箱唯一）。"""

    __tablename__ = "contacts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_contact_user_email"),)
