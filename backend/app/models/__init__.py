"""导入所有模型，确保 Base.metadata 被完整填充（供 Alembic 使用）。"""

from app.models.base import Base
from app.models.email_account import EmailAccount
from app.models.email_sync_log import EmailSyncLog
from app.models.invoice import Invoice
from app.models.seller_category_rule import SellerCategoryRule
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "EmailAccount",
    "Invoice",
    "SellerCategoryRule",
    "EmailSyncLog",
]
