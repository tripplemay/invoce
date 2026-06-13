"""FastAPI 依赖：当前登录用户解析。"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import decode_access_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无效或缺失的认证凭证",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if cred is None:
        raise _CREDENTIALS_EXC
    try:
        payload = decode_access_token(cred.credentials)
        subject = payload.get("sub")
        user_id = uuid.UUID(str(subject))
    except Exception as exc:  # noqa: BLE001
        raise _CREDENTIALS_EXC from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    return user
