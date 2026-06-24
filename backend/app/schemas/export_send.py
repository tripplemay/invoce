"""报销单一键发送的 Pydantic 模型。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ExportSendCreate(BaseModel):
    """从通讯录选联系人 + / 或临时填邮箱，发送某个已完成导出任务的报销单。"""

    contact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    emails: list[EmailStr] = Field(default_factory=list, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_recipient(self) -> "ExportSendCreate":
        if not self.contact_ids and not self.emails:
            raise ValueError("至少选择一个联系人或填写一个邮箱")
        return self


class ExportSendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    export_task_id: uuid.UUID
    to_addresses: list[str]
    subject: str | None
    note: str | None
    delivery_mode: str | None
    status: str
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
