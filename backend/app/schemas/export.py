"""报销单异步导出任务的 Pydantic 模型。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExportTaskCreate(BaseModel):
    invoice_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)
    mark_submitted: bool = True


class ExportTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    invoice_count: int
    mark_submitted: bool
    result_filename: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class ExportDownloadOut(BaseModel):
    url: str
    expires_in: int
