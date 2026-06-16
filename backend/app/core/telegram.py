"""Telegram Bot API 轻量客户端（httpx）：只用到 sendMessage / getFile / 下载 / setWebhook。

不引重型 python-telegram-bot（它自带轮询/事件循环，对 webhook + 几个调用是过度依赖）。
所有函数对网络失败都温和处理（回复 best-effort 吞异常；取文件失败返回 None）。
"""

import httpx

from app.core.config import settings

# Bot API getFile 下载上限 20MB（平台限制）。典型发票远小于此。
MAX_TELEGRAM_FILE_BYTES = 20 * 1024 * 1024
_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


def _api(method: str) -> str:
    return f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/{method}"


async def send_message(chat_id: int, text: str) -> None:
    """回复用户（best-effort，失败不抛——回复失败不应连累入库）。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(_api("sendMessage"), json={"chat_id": chat_id, "text": text})
    except httpx.HTTPError:
        pass


async def get_file_path(file_id: str) -> str | None:
    """getFile → file_path（用于拼下载地址）；任何失败返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_api("getFile"), params={"file_id": file_id})
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return data["result"].get("file_path")
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    return None


async def download_file(
    file_path: str, *, max_bytes: int = MAX_TELEGRAM_FILE_BYTES
) -> bytes | None:
    """下载 file_path 指向的文件，超过 max_bytes 或失败返回 None。"""
    url = f"{settings.telegram_api_base}/file/bot{settings.telegram_bot_token}/{file_path}"
    try:
        async with (
            httpx.AsyncClient(timeout=_TIMEOUT) as client,
            client.stream("GET", url) as resp,
        ):
            if resp.status_code != 200:
                return None
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    return None
    except httpx.HTTPError:
        return None
    return bytes(buf)


async def set_webhook(url: str, secret: str) -> dict:
    """注册 webhook（部署时调用一次）。"""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api("setWebhook"),
            json={"url": url, "secret_token": secret, "allowed_updates": ["message"]},
        )
        return resp.json()
