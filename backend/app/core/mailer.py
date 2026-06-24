"""出站邮件发送底座（aiosmtplib + 标准库 EmailMessage）。

平台统一发件账户：发件人/凭证全部来自 Settings，业务层只管收件人、主题、正文、附件。
对外仅暴露 send_email；附件用 (文件名, 字节内容, MIME) 三元组表示。
"""

import logging
from collections.abc import Sequence
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)

# (filename, content, mime) —— mime 形如 "application/zip"
Attachment = tuple[str, bytes, str]


def _guard_header(value: str) -> str:
    """禁止头部字段含 CR/LF，防 SMTP header 注入（收件人/主题均经此校验）。"""
    if "\r" in value or "\n" in value:
        raise ValueError("邮件字段不可包含换行符")
    return value


def _build_message(
    *, to: Sequence[str], subject: str, body: str, attachments: Sequence[Attachment]
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.outbound_from_name, settings.from_address))
    msg["To"] = ", ".join(_guard_header(addr) for addr in to)
    msg["Subject"] = _guard_header(subject)
    msg.set_content(body)
    for filename, content, mime in attachments:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(
            content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=filename,
        )
    return msg


async def send_email(
    *,
    to: Sequence[str],
    subject: str,
    body: str,
    attachments: Sequence[Attachment] = (),
) -> None:
    """发送一封邮件。失败抛异常，由调用方收口（发送任务转 failed）。"""
    if not settings.outbound_enabled:
        raise RuntimeError("出站发件未启用（未配置 SMTP_HOST）")
    if not to:
        raise ValueError("收件人不能为空")

    msg = _build_message(to=to, subject=subject, body=body, attachments=attachments)
    # 465 用隐式 TLS(use_tls)；587 用 STARTTLS(start_tls)，二者互斥。
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_ssl,
        start_tls=not settings.smtp_use_ssl,
    )
