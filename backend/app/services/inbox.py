"""专属收票邮箱：地址 token 生成（用户名派生 + 去重）与地址解析。"""

import re
import secrets
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

_SANITIZE = re.compile(r"[^a-z0-9._-]+")


def base_from_email(email: str) -> str:
    """从邮箱 localpart 派生基底：小写、只保留 [a-z0-9._-]、压连续分隔、去首尾分隔；空则回退 'user'。"""
    local = (email or "").split("@", 1)[0].lower()
    s = _SANITIZE.sub("-", local)
    s = re.sub(r"[-._]{2,}", "-", s).strip(".-_")
    return s[:40] or "user"


async def generate_inbox_token(session: AsyncSession, email: str) -> str:
    """生成唯一收票 token（用户名派生；冲突时加随机后缀）。"""
    base = base_from_email(email)
    candidate = base
    for _ in range(5):
        taken = await session.scalar(select(User.id).where(User.inbox_token == candidate))
        if taken is None:
            return candidate
        candidate = f"{base}-{secrets.token_hex(2)}"
    return f"{base}-{secrets.token_hex(4)}"  # 极端兜底


def full_address(token: str) -> str:
    """token → 完整收票地址 <token>@<收票域>。"""
    return f"{token}@{settings.inbound_email_domain}"


def token_from_recipient(recipient: str) -> str | None:
    """从收件地址取 localpart 作为 token（去掉 +detail 子地址）；非本域或畸形返回 None。"""
    # 先 NFKC 归一再小写，避免同形字符绕过域名校验（token 本身是 ASCII，归一后失配即 None）
    addr = unicodedata.normalize("NFKC", (recipient or "").strip()).lower()
    if "@" not in addr:
        return None
    local, _, domain = addr.partition("@")
    if settings.inbound_email_domain and domain != settings.inbound_email_domain.lower():
        return None
    return local.split("+", 1)[0] or None
