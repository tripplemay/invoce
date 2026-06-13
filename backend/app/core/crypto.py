"""对称加密：用于落库前加密 IMAP 授权码等敏感凭证（密钥来自 .env 的 FERNET_KEY）。"""

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.fernet_key.encode())


def encrypt(plaintext: str) -> bytes:
    """加密明文字符串，返回密文字节（直接存入 BYTEA 列）。"""
    return _fernet.encrypt(plaintext.encode())


def decrypt(token: bytes) -> str:
    """解密密文字节，返回明文字符串。"""
    return _fernet.decrypt(token).decode()
