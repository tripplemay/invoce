"""共享入库：把发票文件字节落库（file_key 去重 → R2 → 建 Invoice 行）。

手动上传 / Telegram bot 等多入口共用同一条落库路径，避免重复。AI 抽取入队由调用方负责。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.enums import InvoiceStatus, ReimbursementStatus
from app.models.invoice import Invoice


def detect_file_type(content: bytes) -> tuple[str, str] | None:
    """按魔数判定类型，不信任声明的 Content-Type。返回 (扩展名, content_type) 或 None。"""
    if content[:4] == b"%PDF":
        return (".pdf", "application/pdf")
    if content[:8].startswith(b"\x89PNG\r\n\x1a\n"):
        return (".png", "image/png")
    if content[:3] == b"\xff\xd8\xff":
        return (".jpg", "image/jpeg")
    return None


async def persist_invoice_bytes(
    session: AsyncSession,
    user_id: uuid.UUID,
    content: bytes,
    ext: str,
    ctype: str,
    source: str,
) -> Invoice | None:
    """落库一张发票：同用户同文件(file_key=sha256)已存在则跳过(去重)，返回新建 Invoice 或 None。

    用 SAVEPOINT 隔离单条插入：并发下撞 (user_id, file_key) 唯一约束即视为已存在、跳过，
    不连累同批其它文件。
    """
    key = storage.build_key(str(user_id), content, ext)
    if await session.scalar(
        select(Invoice.id).where(Invoice.user_id == user_id, Invoice.file_key == key)
    ):
        return None  # 快路径去重
    await storage.upload_bytes(key, content, ctype)
    inv = Invoice(
        user_id=user_id,
        file_key=key,
        source=source,
        status=InvoiceStatus.PROCESSING.value,
        reimbursement_status=ReimbursementStatus.UNREIMBURSED.value,
    )
    try:
        async with session.begin_nested():
            session.add(inv)
            await session.flush()
    except IntegrityError:
        return None
    return inv
