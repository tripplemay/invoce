"""邮箱账户 Pydantic 模型。注意：auth_code 仅入参，绝不出参。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailAccountCreate(BaseModel):
    imap_user: str = Field(min_length=1, max_length=255)
    auth_code: str = Field(
        min_length=1, max_length=128, description="16 位授权码（明文入参，服务端加密存储）"
    )
    imap_host: str = "imap.qq.com"
    imap_port: int = 993
    enabled: bool = True


class EmailAccountUpdate(BaseModel):
    auth_code: str | None = Field(default=None, min_length=1, max_length=128)
    imap_host: str | None = None
    imap_port: int | None = None
    enabled: bool | None = None


class EmailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    imap_user: str
    imap_host: str
    imap_port: int
    enabled: bool
    last_sync_uid: int | None
    created_at: datetime
