"""开票方→分类 学习记忆：用户纠正分类后记录，后续同开票方自动套用。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller_category_rule import SellerCategoryRule


async def get_rule(
    session: AsyncSession, user_id: uuid.UUID, seller_name: str
) -> SellerCategoryRule | None:
    return await session.scalar(
        select(SellerCategoryRule).where(
            SellerCategoryRule.user_id == user_id,
            SellerCategoryRule.seller_name == seller_name,
        )
    )


async def upsert_rule(
    session: AsyncSession, user_id: uuid.UUID, seller_name: str, category: str
) -> None:
    """记录/更新映射规则（不提交，由调用方统一提交）。"""
    rule = await get_rule(session, user_id, seller_name)
    if rule is None:
        session.add(SellerCategoryRule(user_id=user_id, seller_name=seller_name, category=category))
    elif rule.category != category:
        rule.category = category
