"""Telegram 绑定相关 Pydantic 模型。"""

import uuid

from pydantic import BaseModel, ConfigDict


class TelegramLinkOut(BaseModel):
    """生成的一次性绑定深链。"""

    code: str
    deep_link: str  # https://t.me/<bot>?start=<code>
    expires_in: int


class TelegramAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: int
    username: str | None
    enabled: bool
