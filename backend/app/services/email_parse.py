"""邮件解析（纯函数，可测）：关键词匹配 + 提取发票文件（附件 / HTML 内嵌 Base64 图 / 外链图 URL）。"""

import base64
import re
from email.header import decode_header
from email.message import Message

KEYWORDS = ("发票", "电子发票", "行程单", "invoice")

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}

_DATA_URI_RE = re.compile(r"data:(image/(?:png|jpe?g));base64,([A-Za-z0-9+/=\s]+)", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


def decode_mime_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = []
    for value, charset in decode_header(raw):
        if isinstance(value, bytes):
            parts.append(value.decode(charset or "utf-8", errors="ignore"))
        else:
            parts.append(value)
    return "".join(parts)


def _norm_ctype(ctype: str) -> str:
    return "image/jpeg" if ctype.lower() in ("image/jpg",) else ctype.lower()


def matches_keywords(subject: str, body: str) -> bool:
    hay = f"{subject or ''} {body or ''}".lower()
    return any(k.lower() in hay for k in KEYWORDS)


def body_text(msg: Message) -> str:
    """收集 text/plain 与 text/html（粗略去标签）文本，用于关键词匹配。"""
    chunks: list[str] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes | bytearray):
                continue
            text = bytes(payload).decode(part.get_content_charset() or "utf-8", errors="ignore")
            if ctype == "text/html":
                text = re.sub(r"<[^>]+>", " ", text)
            chunks.append(text)
    return " ".join(chunks)


def html_parts(msg: Message) -> list[str]:
    out: list[str] = []
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes | bytearray):
                out.append(
                    bytes(payload).decode(part.get_content_charset() or "utf-8", errors="ignore")
                )
    return out


def extract_attachments(msg: Message) -> list[tuple[bytes, str]]:
    files: list[tuple[bytes, str]] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype not in ALLOWED_TYPES:
            continue
        if part.get_content_disposition() == "attachment" or part.get_filename():
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes | bytearray):
                files.append((bytes(payload), _norm_ctype(ctype)))
    return files


def extract_inline_base64_images(html: str) -> list[tuple[bytes, str]]:
    files: list[tuple[bytes, str]] = []
    for m in _DATA_URI_RE.finditer(html):
        ctype = _norm_ctype(m.group(1))
        try:
            data = base64.b64decode(re.sub(r"\s", "", m.group(2)))
            files.append((data, ctype))
        except (ValueError, TypeError):
            continue
    return files


def extract_external_image_urls(html: str) -> list[str]:
    return _IMG_SRC_RE.findall(html)
