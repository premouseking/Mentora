"""
对象存储抽象：本地 MinIO 与云端 S3/COS 同构。

约定：
- 数据库只保存 object_key / artifact_ref，不保存本地绝对路径
- filesystem 后端仅用于测试与无 Docker 的 CI，生产使用 s3 后端

约束：
- bucket 名称与 endpoint 来自环境变量
- 预签名 URL 仅用于客户端直传原始文件

@see docs/architecture/end-to-end-implementation-plan.md
@module mentora/common/storage
"""

import os
from pathlib import Path
from typing import BinaryIO

from django.conf import settings


class ObjectStorageError(Exception):
    """对象存储操作失败。"""


class ObjectStorageService:
    """S3 兼容对象存储服务；测试环境可切换为本地文件系统。"""

    def __init__(self) -> None:
        self.backend = settings.OBJECT_STORAGE_BACKEND
        self.bucket = settings.OBJECT_STORAGE_BUCKET
        self.fs_root = Path(settings.OBJECT_STORAGE_FS_ROOT)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._client_for_endpoint(settings.OBJECT_STORAGE_ENDPOINT)
        return self._client

    def _client_for_endpoint(self, endpoint_url: str):
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY,
            region_name=settings.OBJECT_STORAGE_REGION,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """确保 bucket 存在（开发/测试环境自动创建）。"""
        if self.backend == "filesystem":
            self.fs_root.mkdir(parents=True, exist_ok=True)
            return

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def _fs_path(self, key: str) -> Path:
        return self.fs_root / self.bucket / key

    def put_object(self, key: str, body: bytes | BinaryIO, content_type: str = "") -> None:
        if self.backend == "filesystem":
            path = self._fs_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = body if isinstance(body, bytes) else body.read()
            path.write_bytes(data)
            return

        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, **extra)

    def get_object_bytes(self, key: str) -> bytes:
        if self.backend == "filesystem":
            path = self._fs_path(key)
            if not path.exists():
                raise ObjectStorageError(f"对象不存在: {key}")
            return path.read_bytes()

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError(f"读取对象失败 ({key}): {exc}") from exc

    def get_object_bytes_range(self, key: str, start: int, end: int) -> bytes:
        """读取对象字节区间（含 end）。"""
        if start < 0 or end < start:
            raise ObjectStorageError(f"无效的字节区间: {start}-{end}")

        if self.backend == "filesystem":
            path = self._fs_path(key)
            if not path.exists():
                raise ObjectStorageError(f"对象不存在: {key}")
            with path.open("rb") as handle:
                handle.seek(start)
                return handle.read(end - start + 1)

        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
                Range=f"bytes={start}-{end}",
            )
            return response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError(f"读取对象区间失败 ({key}): {exc}") from exc

    def head_object(self, key: str) -> dict:
        if self.backend == "filesystem":
            path = self._fs_path(key)
            if not path.exists():
                raise ObjectStorageError(f"对象不存在: {key}")
            return {"ContentLength": path.stat().st_size}

        return self.client.head_object(Bucket=self.bucket, Key=key)

    def generate_presigned_put_url(self, key: str, expires: int = 3600) -> str:
        if self.backend == "filesystem":
            # 文件系统后端无 HTTP PUT；开发 smoke 直接 put_object
            return f"filesystem://{self.bucket}/{key}"

        # 浏览器直传须用公网可达 endpoint；服务端读写仍走 OBJECT_STORAGE_ENDPOINT
        client = (
            self.client
            if settings.OBJECT_STORAGE_PUBLIC_ENDPOINT == settings.OBJECT_STORAGE_ENDPOINT
            else self._client_for_endpoint(settings.OBJECT_STORAGE_PUBLIC_ENDPOINT)
        )
        return client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    def upload_key_for_session(self, upload_id: str, filename: str = "original.pdf") -> str:
        safe_name = os.path.basename(filename) or "original.pdf"
        return f"uploads/{upload_id}/{safe_name}"

    def artifact_key_for_bundle(self, bundle_id: str) -> str:
        return f"artifacts/{bundle_id}.json"
