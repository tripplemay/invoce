"""S3 兼容对象存储客户端（boto3）。私有桶，按 user_id 前缀隔离，预签名 URL 安全预览。"""

import asyncio
import hashlib
from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def _client():  # noqa: ANN202
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        config=Config(signature_version="s3v4"),
    )


def file_hash(data: bytes) -> str:
    """文件内容 SHA-256，作为 file_key 主体（天然文件级去重）。"""
    return hashlib.sha256(data).hexdigest()


def build_key(user_id: str, data: bytes, ext: str) -> str:
    """对象 Key：user_id/<sha256><ext>，按用户隔离。"""
    return f"{user_id}/{file_hash(data)}{ext}"


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    def _put() -> None:
        _client().put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
        )

    await asyncio.to_thread(_put)


async def download_bytes(key: str) -> bytes:
    def _get() -> bytes:
        resp = _client().get_object(Bucket=settings.s3_bucket, Key=key)
        return resp["Body"].read()

    return await asyncio.to_thread(_get)


async def presigned_get_url(key: str, expires: int | None = None) -> str:
    def _sign() -> str:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires or settings.presigned_expire_seconds,
        )

    return await asyncio.to_thread(_sign)
