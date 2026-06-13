"""邮箱账户 CRUD：授权码 Fernet 加密存储，按用户隔离。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.crypto import encrypt
from app.core.db import get_session
from app.models.email_account import EmailAccount
from app.models.user import User
from app.schemas.email_account import (
    EmailAccountCreate,
    EmailAccountOut,
    EmailAccountUpdate,
)

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


async def _get_owned(account_id: uuid.UUID, user: User, session: AsyncSession) -> EmailAccount:
    acct = await session.get(EmailAccount, account_id)
    if acct is None or acct.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邮箱账户不存在")
    return acct


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[EmailAccount]:
    rows = await session.scalars(
        select(EmailAccount)
        .where(EmailAccount.user_id == user.id)
        .order_by(EmailAccount.created_at)
    )
    return list(rows)


@router.post("", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: EmailAccountCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EmailAccount:
    acct = EmailAccount(
        user_id=user.id,
        imap_user=data.imap_user,
        auth_code_enc=encrypt(data.auth_code),
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        enabled=data.enabled,
    )
    session.add(acct)
    await session.commit()
    await session.refresh(acct)
    return acct


@router.patch("/{account_id}", response_model=EmailAccountOut)
async def update_account(
    account_id: uuid.UUID,
    data: EmailAccountUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EmailAccount:
    acct = await _get_owned(account_id, user, session)
    if data.auth_code is not None:
        acct.auth_code_enc = encrypt(data.auth_code)
    if data.imap_host is not None:
        acct.imap_host = data.imap_host
    if data.imap_port is not None:
        acct.imap_port = data.imap_port
    if data.enabled is not None:
        acct.enabled = data.enabled
    await session.commit()
    await session.refresh(acct)
    return acct


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    acct = await _get_owned(account_id, user, session)
    await session.delete(acct)
    await session.commit()
