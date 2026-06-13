"""健康检查端点。"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探针（不依赖数据库）。"""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """就绪探针：验证数据库可连通。"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
