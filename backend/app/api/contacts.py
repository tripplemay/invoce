"""通讯录 CRUD：下游处理人联系人，按用户隔离，同一用户邮箱唯一。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.contact import Contact
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


async def _get_owned(contact_id: uuid.UUID, user: User, session: AsyncSession) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "联系人不存在")
    return contact


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[Contact]:
    rows = await session.scalars(
        select(Contact).where(Contact.user_id == user.id).order_by(Contact.name)
    )
    return list(rows)


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    contact = Contact(user_id=user.id, name=data.name, email=str(data.email), note=data.note)
    session.add(contact)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已在通讯录中") from None
    await session.refresh(contact)
    return contact


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    contact = await _get_owned(contact_id, user, session)
    if data.name is not None:
        contact.name = data.name
    if data.email is not None:
        contact.email = str(data.email)
    if data.note is not None:
        contact.note = data.note
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已在通讯录中") from None
    await session.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    contact = await _get_owned(contact_id, user, session)
    await session.delete(contact)
    await session.commit()
