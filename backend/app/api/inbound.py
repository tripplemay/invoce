"""专属收票邮箱：入站 webhook（Cloudflare Email Worker → 后端）+ 用户查询收票地址。"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.queue import get_pool
from app.models.user import User
from app.schemas.inbox import InboxOut
from app.services import inbox

router = APIRouter(tags=["inbound"])

# Cloudflare Email Worker 上限 25 MiB；后端略放宽到 26 MB 兜底。
MAX_INBOUND_BYTES = 26 * 1024 * 1024


@router.post("/inbound/email", include_in_schema=False)
async def inbound_email(
    request: Request,
    x_inbound_secret: str | None = Header(default=None),
    x_original_to: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    """Cloudflare Email Worker 把原始邮件 POST 到这里（body=raw MIME，header=收件人+共享密钥）。

    非 2xx 会让 Worker setReject（拒信），因此鉴权失败必须返回 4xx 而非 200。
    """
    if not settings.inbound_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "inbound disabled")
    secret = settings.inbound_webhook_secret
    # 常量时间比较，避免按字节计时爆破共享密钥
    if not secret or not secrets.compare_digest(x_inbound_secret or "", secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")
    # 鉴权通过后，先看 Content-Length 把超大请求挡在读 body 之前
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_INBOUND_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "email too large")
    token = inbox.token_from_recipient(x_original_to or "")
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown recipient")
    user_id = await session.scalar(select(User.id).where(User.inbox_token == token))
    if user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown recipient")
    raw = await request.body()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty body")
    if len(raw) > MAX_INBOUND_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "email too large")
    pool = await get_pool()
    try:
        await pool.enqueue_job("process_inbound_email", str(user_id), raw)
    finally:
        await pool.aclose()
    return {"ok": True}


@router.get("/inbox", response_model=InboxOut)
async def get_inbox(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InboxOut:
    """返回当前用户的专属收票地址；老用户缺 token 时惰性补发。"""
    if not user.inbox_token:
        user.inbox_token = await inbox.generate_inbox_token(session, user.email)
        await session.commit()
    return InboxOut(
        token=user.inbox_token,
        address=inbox.full_address(user.inbox_token) if settings.inbound_enabled else None,
        enabled=settings.inbound_enabled,
    )
