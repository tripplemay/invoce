from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 专属收票邮箱的 localpart（<inbox_token>@<收票域>）；注册时生成，唯一。
    inbox_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
