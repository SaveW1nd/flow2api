"""对象存储:把 FLOW 返回的资源转存到 MinIO/S3,得到稳定的可下载 URL。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import boto3
import httpx
from botocore.client import Config

from app.core.config import settings

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
    return _s3


def ensure_bucket() -> None:
    s3 = get_s3()
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if settings.S3_BUCKET not in existing:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
    # 生成的图片/视频 URL 直接用于前端 <img>/<video>,需允许匿名只读。
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{settings.S3_BUCKET}/*"],
            }
        ],
    }
    try:
        s3.put_bucket_policy(Bucket=settings.S3_BUCKET, Policy=json.dumps(policy))
    except Exception:  # noqa: BLE001
        pass


_EXT = {"image": "png", "video": "mp4"}
_CONTENT_TYPE = {"image": "image/png", "video": "video/mp4"}


def _local_url_for_key(key: str) -> str:
    normalized = key.replace("\\", "/")
    return f"{settings.MEDIA_PUBLIC_ENDPOINT.rstrip('/')}/{normalized}"


def _store_local(content: bytes, asset_type: str, user_id: int, ext: str | None = None) -> str:
    ext = ext or _EXT.get(asset_type, "bin")
    key = f"{asset_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    path = Path(settings.MEDIA_DIR) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _local_url_for_key(key)


def store_bytes(content: bytes, asset_type: str, user_id: int, ext: str | None = None) -> str:
    """把生成的二进制资源存入对象存储,返回公网可访问 URL。"""
    ext = ext or _EXT.get(asset_type, "bin")
    key = f"{asset_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    try:
        get_s3().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=content,
            ContentType=_CONTENT_TYPE.get(asset_type, "application/octet-stream"),
        )
        return f"{settings.S3_PUBLIC_ENDPOINT}/{settings.S3_BUCKET}/{key}"
    except Exception:  # noqa: BLE001
        return _store_local(content, asset_type, user_id, ext=ext)


def store_remote_asset(url: str, asset_type: str, user_id: int, proxy: str | None = None) -> str:
    """下载远端资源并存入对象存储,返回公网可访问 URL。"""
    ext = _EXT.get(asset_type, "bin")
    key = f"{asset_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    with httpx.Client(timeout=min(45, settings.FLOW_REQUEST_TIMEOUT), follow_redirects=True, proxy=proxy) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content

    try:
        get_s3().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=content,
            ContentType=_CONTENT_TYPE.get(asset_type, "application/octet-stream"),
        )
        return f"{settings.S3_PUBLIC_ENDPOINT}/{settings.S3_BUCKET}/{key}"
    except Exception:  # noqa: BLE001
        return _store_local(content, asset_type, user_id, ext=ext)
