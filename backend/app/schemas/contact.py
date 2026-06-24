"""通讯录 Pydantic 模型。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    note: str | None = Field(default=None, max_length=255)


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    note: str | None = Field(default=None, max_length=255)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    note: str | None
    created_at: datetime
