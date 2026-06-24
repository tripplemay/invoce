"""出站邮件发送底座测试（aiosmtplib 已 mock，不发真实邮件）。"""

import pytest

from app.core import mailer
from app.core.config import settings


@pytest.fixture
def smtp_on(monkeypatch):
    """临时把发件配置打开，避免依赖真实 .env。"""
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_port", 465)
    monkeypatch.setattr(settings, "smtp_user", "bot@test.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_use_ssl", True)
    monkeypatch.setattr(settings, "outbound_from_address", "noreply@test.com")
    monkeypatch.setattr(settings, "outbound_from_name", "发票助手")


@pytest.fixture
def captured(monkeypatch):
    """拦截 aiosmtplib.send，记录被发送的 EmailMessage 与连接参数。"""
    box: dict = {}

    async def _fake_send(message, **kwargs):
        box["message"] = message
        box["kwargs"] = kwargs

    monkeypatch.setattr("app.core.mailer.aiosmtplib.send", _fake_send)
    return box


async def test_send_email_builds_message_with_attachment(smtp_on, captured) -> None:
    await mailer.send_email(
        to=["a@x.com", "b@y.com"],
        subject="报销材料",
        body="正文内容",
        attachments=[("报销单.zip", b"PK\x03\x04zip", "application/zip")],
    )
    msg = captured["message"]
    assert msg["To"] == "a@x.com, b@y.com"
    assert msg["Subject"] == "报销材料"
    # 发件人含显示名 + 地址
    assert "noreply@test.com" in msg["From"] and "发票助手" in msg["From"]
    # 附件落在 multipart 中
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "报销单.zip"
    assert attachments[0].get_payload(decode=True) == b"PK\x03\x04zip"
    # 走隐式 TLS（465）
    assert captured["kwargs"]["hostname"] == "smtp.test"
    assert captured["kwargs"]["use_tls"] is True


async def test_send_email_without_attachment(smtp_on, captured) -> None:
    await mailer.send_email(to=["a@x.com"], subject="标题", body="只有正文")
    msg = captured["message"]
    assert list(msg.iter_attachments()) == []
    assert "只有正文" in msg.get_content()


async def test_send_email_rejects_header_injection(smtp_on, captured) -> None:
    """收件人/主题含 CR/LF 必须拒绝，防 SMTP header 注入。"""
    with pytest.raises(ValueError):
        await mailer.send_email(to=["ok@x.com\r\nBcc: evil@x.com"], subject="t", body="b")
    with pytest.raises(ValueError):
        await mailer.send_email(to=["ok@x.com"], subject="t\nX-Inject: 1", body="b")
    # 注入被拦下，未触达 SMTP
    assert "message" not in captured


async def test_send_email_disabled_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    with pytest.raises(RuntimeError):
        await mailer.send_email(to=["a@x.com"], subject="t", body="b")


async def test_send_email_empty_recipients_raises(smtp_on) -> None:
    with pytest.raises(ValueError):
        await mailer.send_email(to=[], subject="t", body="b")
