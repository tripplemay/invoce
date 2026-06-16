"""S3 兼容对象存储客户端（boto3）。私有桶，按 user_id 前缀隔离，预签名 URL 安全预览。"""

import asyncio
import contextlib
import hashlib
import urllib.parse
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


async def delete_object(key: str) -> None:
    """删除对象（best-effort）：删发票行已成功，对象存储清理失败不应阻断或回滚，故吞掉异常。"""

    def _del() -> None:
        # 孤儿文件清理失败可接受，不连累删除主流程
        with contextlib.suppress(Exception):
            _client().delete_object(Bucket=settings.s3_bucket, Key=key)

    await asyncio.to_thread(_del)


async def presigned_get_url(
    key: str, expires: int | None = None, download_filename: str | None = None
) -> str:
    params: dict[str, str] = {"Bucket": settings.s3_bucket, "Key": key}
    if download_filename:
        # 让浏览器按附件下载并用友好文件名（RFC 5987，兼容中文名）。
        quoted = urllib.parse.quote(download_filename)
        params["ResponseContentDisposition"] = f"attachment; filename*=UTF-8''{quoted}"

    def _sign() -> str:
        return _client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires or settings.presigned_expire_seconds,
        )

    return await asyncio.to_thread(_sign)
