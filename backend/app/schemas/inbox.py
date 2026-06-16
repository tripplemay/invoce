"""专属收票邮箱相关 Pydantic 模型。"""

from pydantic import BaseModel


class InboxOut(BaseModel):
    token: str
    address: str | None  # <token>@<收票域>；未配置收票域时为 None
    enabled: bool
