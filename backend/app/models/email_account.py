import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class EmailAccount(UUIDPKMixin, TimestampMixin, Base):
    """用户的 QQ 邮箱 IMAP 配置。授权码加密存储，取代全局 .env 配置（多用户必需）。"""

    __tablename__ = "email_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    imap_user: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet 加密后的 16 位授权码
    auth_code_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    imap_host: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="imap.qq.com"
    )
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="993")
    # 已处理到的最大邮件 UID，用于幂等去重（不改邮件已读状态）
    last_sync_uid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
