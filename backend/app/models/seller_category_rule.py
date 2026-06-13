import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class SellerCategoryRule(UUIDPKMixin, TimestampMixin, Base):
    """开票方→分类 的学习记忆：用户手动纠正分类后记录，后续同开票方自动套用。"""

    __tablename__ = "seller_category_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seller_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "seller_name", name="uq_seller_category_rule"),)
