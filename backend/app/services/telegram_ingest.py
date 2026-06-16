"""Telegram bot 消息处理：/start 绑定 + 文件入库。由 worker 调用（webhook 已快速 200）。

容错优先：任何分支失败都尽量回复用户、不抛异常（webhook 早已应答）。
"""

import uuid

from arq.connections import ArqRedis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import telegram
from app.models.enums import InvoiceSource
from app.models.telegram_account import TelegramAccount
from app.services import email_parse
from app.services.ingest import detect_file_type, persist_invoice_bytes

LINK_CODE_PREFIX = "tg:link:"
_HELP = (
    "把发票文件(PDF / 图片 / ZIP)发给我即可自动入库。\n"
    "还没绑定?请在网页端打开「绑定 Telegram」生成绑定链接。"
)


def _extract_file_id(message: dict) -> str | None:
    """从消息取文件 file_id：document 直接取；photo 取最大尺寸（数组最后一项）。"""
    doc = message.get("document")
    if isinstance(doc, dict) and doc.get("file_id"):
        return str(doc["file_id"])
    photos = message.get("photo")
    if isinstance(photos, list) and photos and isinstance(photos[-1], dict):
        fid = photos[-1].get("file_id")
        return str(fid) if fid else None
    return None


async def _ingest_bytes(session: AsyncSession, user_id: uuid.UUID, content: bytes) -> list[str]:
    """按 PDF/图片/ZIP 入库，返回新建发票 id 列表（走共享去重/落库；source=telegram）。"""
    created: list[str] = []
    if content[:4] == b"PK\x03\x04":
        for pdf in email_parse.pdfs_from_zip_bytes(content):
            inv = await persist_invoice_bytes(
                session, user_id, pdf, ".pdf", "application/pdf", InvoiceSource.TELEGRAM.value
            )
            if inv is not None:
                created.append(str(inv.id))
    else:
        detected = detect_file_type(content)
        if detected is not None:
            ext, ctype = detected
            inv = await persist_invoice_bytes(
                session, user_id, content, ext, ctype, InvoiceSource.TELEGRAM.value
            )
            if inv is not None:
                created.append(str(inv.id))
    return created


async def _bind(
    session: AsyncSession, redis: ArqRedis, chat_id: int, message: dict, code: str
) -> None:
    if not code:
        await telegram.send_message(
            chat_id, "请先在网页端「绑定 Telegram」生成绑定链接，再点开它。"
        )
        return
    raw = await redis.get(f"{LINK_CODE_PREFIX}{code}")
    if not raw:
        await telegram.send_message(chat_id, "绑定码无效或已过期，请在网页端重新生成。")
        return
    await redis.delete(f"{LINK_CODE_PREFIX}{code}")
    user_id = uuid.UUID(raw.decode() if isinstance(raw, bytes | bytearray) else str(raw))
    username = (message.get("from") or {}).get("username")
    # 清掉该 chat 或该用户的旧绑定，支持改绑（避免唯一约束冲突）
    olds = await session.scalars(
        select(TelegramAccount).where(
            or_(TelegramAccount.chat_id == chat_id, TelegramAccount.user_id == user_id)
        )
    )
    for acc in olds:
        await session.delete(acc)
    await session.flush()
    session.add(TelegramAccount(user_id=user_id, chat_id=chat_id, username=username))
    await session.commit()
    await telegram.send_message(
        chat_id, "✅ 绑定成功！现在把发票文件(PDF/图片/ZIP)发给我即可自动入库。"
    )


async def _handle_file(session: AsyncSession, redis: ArqRedis, chat_id: int, file_id: str) -> None:
    account = await session.scalar(
        select(TelegramAccount).where(
            TelegramAccount.chat_id == chat_id, TelegramAccount.enabled.is_(True)
        )
    )
    if account is None:
        await telegram.send_message(
            chat_id, "你还没绑定账号。请在网页端「绑定 Telegram」后再发文件。"
        )
        return
    user_id = account.user_id
    path = await telegram.get_file_path(file_id)
    data = await telegram.download_file(path) if path else None
    if not data:
        await telegram.send_message(chat_id, "文件下载失败或超过 20MB，请重试或改用网页上传。")
        return
    created = await _ingest_bytes(session, user_id, data)
    if not created:
        await session.rollback()
        await telegram.send_message(
            chat_id, "没找到可识别的发票(需 PDF/图片，或含发票 PDF 的 ZIP)。"
        )
        return
    await session.commit()
    for inv_id in created:
        await redis.enqueue_job("extract_invoice", inv_id)
    await telegram.send_message(chat_id, f"✅ 已入库 {len(created)} 张发票，正在识别。")


async def process_update(session: AsyncSession, redis: ArqRedis, update: dict) -> None:
    """处理单条 Telegram update。"""
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return
    text = (message.get("text") or "").strip()
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        await _bind(session, redis, chat_id, message, code)
        return
    file_id = _extract_file_id(message)
    if file_id:
        await _handle_file(session, redis, chat_id, file_id)
        return
    await telegram.send_message(chat_id, _HELP)
