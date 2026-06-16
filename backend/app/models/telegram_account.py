import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class TelegramAccount(UUIDPKMixin, TimestampMixin, Base):
    """用户绑定的 Telegram 账号：bot 收到该 chat 的文件即入到该用户名下。一用户一绑定。"""

    __tablename__ = "telegram_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # Telegram chat id 可能很大，用 BigInteger；一个 chat 只绑一个用户。
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
