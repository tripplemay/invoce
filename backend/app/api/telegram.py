"""Telegram：webhook 接收(非鉴权,靠 secret 校验) + 网页端绑定码/状态/解绑(鉴权)。"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.queue import get_pool
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.schemas.telegram import TelegramAccountOut, TelegramLinkOut
from app.services.telegram_ingest import LINK_CODE_PREFIX

router = APIRouter(prefix="/telegram", tags=["telegram"])

_CODE_TTL = 600  # 绑定码有效期 10 分钟


@router.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Telegram 推送入口：校验 secret → 入队异步处理 → 立即 200（Telegram 要求秒回）。"""
    if (
        not settings.telegram_webhook_secret
        or x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001 解析失败也回 200，避免 Telegram 重试风暴
        return {"ok": True}
    pool = await get_pool()
    try:
        await pool.enqueue_job("process_telegram_update", update)
    finally:
        await pool.aclose()
    return {"ok": True}


@router.post("/link-code", response_model=TelegramLinkOut)
async def create_link_code(user: User = Depends(get_current_user)) -> TelegramLinkOut:
    """生成一次性绑定码 + 深链；用户点开深链发 /start <code> 即完成绑定。"""
    if not settings.telegram_enabled or not settings.telegram_bot_username:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram 功能未配置")
    code = secrets.token_urlsafe(16)
    pool = await get_pool()
    try:
        await pool.set(f"{LINK_CODE_PREFIX}{code}", str(user.id), ex=_CODE_TTL)
    finally:
        await pool.aclose()
    return TelegramLinkOut(
        code=code,
        deep_link=f"https://t.me/{settings.telegram_bot_username}?start={code}",
        expires_in=_CODE_TTL,
    )


@router.get("/account", response_model=TelegramAccountOut | None)
async def get_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TelegramAccount | None:
    return await session.scalar(select(TelegramAccount).where(TelegramAccount.user_id == user.id))


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def unlink(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    acc = await session.scalar(select(TelegramAccount).where(TelegramAccount.user_id == user.id))
    if acc is not None:
        await session.delete(acc)
        await session.commit()
