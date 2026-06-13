"""安全加固单元测试：SSRF 防护 / 魔数检测 / 生产密钥 fail-fast。"""

import pytest

from app.api.invoices import detect_file_type
from app.core import netguard
from app.core.config import Settings


def test_detect_file_type() -> None:
    assert detect_file_type(b"%PDF-1.4 xxx") == (".pdf", "application/pdf")
    assert detect_file_type(b"\x89PNG\r\n\x1a\nxxx") == (".png", "image/png")
    assert detect_file_type(b"\xff\xd8\xff\xe0xxx") == (".jpg", "image/jpeg")
    assert detect_file_type(b"hello world") is None


def test_netguard_blocks_private() -> None:
    assert not netguard.is_safe_url("http://127.0.0.1/x")
    assert not netguard.is_safe_url("http://169.254.169.254/latest/meta-data")
    assert not netguard.is_safe_url("http://10.0.0.5/a.png")
    assert not netguard.is_safe_url("ftp://example.com/x")
    assert netguard.is_safe_url("https://8.8.8.8/a.png")  # 公网字面 IP，无需 DNS


def test_netguard_literal_host() -> None:
    assert netguard.is_blocked_literal_host("localhost")
    assert netguard.is_blocked_literal_host("192.168.1.1")
    assert netguard.is_blocked_literal_host("")
    assert not netguard.is_blocked_literal_host("imap.qq.com")


def test_prod_rejects_default_secrets() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")  # 默认密钥应被拒绝
