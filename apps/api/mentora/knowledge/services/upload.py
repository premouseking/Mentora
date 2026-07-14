"""
上传会话创建与完成校验。

约定：
- complete 时创建 Source + SourceVersion，触发解析入库
- uploadId 由客户端在 create 时提供或服务器生成
- 浏览器在 HTTP 非 localhost 下无 crypto.subtle，可省略 sha256 由服务端从对象存储计算

@module mentora/knowledge/services/upload
"""

import hashlib
import uuid

from django.db import transaction
from django.utils import timezone

from mentora.common.storage import ObjectStorageError, ObjectStorageService
from mentora.knowledge.models import (
    ProcessingStatus,
    Source,
    SourceStatus,
    SourceVersion,
    UploadSession,
    UploadSessionStatus,
)
from mentora.knowledge.services.processing import run_processing_for_version


def create_upload_session(
    owner,
    upload_id: str | None = None,
    byte_size: int | None = None,
    filename: str = "original.pdf",
    media_type: str = "application/pdf",
) -> dict:
    """创建上传会话并返回预签名 PUT URL。"""
    if owner is None or not getattr(owner, "is_authenticated", False):
        raise ValueError("缺少认证用户")
    storage = ObjectStorageService()
    storage.ensure_bucket()

    session_id = upload_id or str(uuid.uuid4())
    object_key = storage.upload_key_for_session(session_id, filename)

    session, _ = UploadSession.objects.update_or_create(
        id=session_id,
        defaults={
            "owner": owner,
            "object_key": object_key,
            "status": UploadSessionStatus.PENDING,
            "expected_byte_size": byte_size,
            "media_type": media_type,
            "original_filename": filename,
            "content_sha256": "",
            "completed_at": None,
        },
    )

    upload_url = storage.generate_presigned_put_url(object_key)
    return {
        "uploadId": str(session.id),
        "uploadUrl": upload_url,
        "objectKey": object_key,
    }


def _hash_object_key(storage: ObjectStorageService, object_key: str) -> str:
    """从对象存储读取内容并计算 SHA-256（HTTP 客户端无法算哈希时的兜底）。"""
    digest = hashlib.sha256()
    digest.update(storage.get_object_bytes(object_key))
    return digest.hexdigest()


def complete_upload(
    upload_id: str,
    content_sha256: str | None,
    byte_size: int,
    owner=None,
    sync_processing: bool = True,
) -> dict:
    """校验上传对象并创建 SourceVersion，可选同步解析。"""
    if owner is None or not getattr(owner, "is_authenticated", False):
        raise ValueError("缺少认证用户")
    storage = ObjectStorageService()

    try:
        session = UploadSession.objects.get(id=upload_id, owner=owner)
    except UploadSession.DoesNotExist:
        raise ValueError("上传会话不存在")

    if session.status == UploadSessionStatus.COMPLETED and session.source_version_id:
        sv = session.source_version
        return {
            "sourceId": str(sv.source_id),
            "sourceVersionId": str(sv.id),
            "processingStatus": sv.processing_status,
        }

    try:
        head = storage.head_object(session.object_key)
    except ObjectStorageError as exc:
        raise ValueError(f"对象存储中找不到上传文件: {exc}") from exc

    actual_size = int(head.get("ContentLength", 0))
    if actual_size != byte_size:
        raise ValueError(f"文件大小不匹配: 期望 {byte_size}, 实际 {actual_size}")

    resolved_sha256 = (content_sha256 or "").strip().lower()
    if not resolved_sha256:
        resolved_sha256 = _hash_object_key(storage, session.object_key)
    elif len(resolved_sha256) != 64:
        raise ValueError("sha256 格式无效")

    with transaction.atomic():
        source = Source.objects.create(
            owner=owner,
            display_title=session.original_filename or "未命名资料",
            status=SourceStatus.ACTIVE,
        )
        source_version = SourceVersion.objects.create(
            source=source,
            version_number=1,
            content_sha256=resolved_sha256,
            object_key=session.object_key,
            media_type=session.media_type,
            byte_size=byte_size,
            original_filename=session.original_filename,
            processing_status=ProcessingStatus.PENDING,
        )
        source.latest_version = source_version
        source.save(update_fields=["latest_version"])

        session.status = UploadSessionStatus.COMPLETED
        session.content_sha256 = resolved_sha256
        session.source_version = source_version
        session.completed_at = timezone.now()
        session.save()

    run_processing_for_version(str(source_version.id), sync=sync_processing)

    source_version.refresh_from_db()
    return {
        "sourceId": str(source.id),
        "sourceVersionId": str(source_version.id),
        "processingStatus": source_version.processing_status,
        "displayTitle": source.display_title,
    }


def upload_file_direct(
    file_bytes: bytes,
    filename: str,
    content_sha256: str,
    owner=None,
    sync_processing: bool = True,
) -> dict:
    """
    直接上传文件到对象存储并走完 complete 流程（seed/smoke 用，不经 HTTP PUT）。
    """
    created = create_upload_session(
        owner=owner,
        byte_size=len(file_bytes),
        filename=filename,
    )
    storage = ObjectStorageService()
    storage.put_object(created["objectKey"], file_bytes, content_type="application/pdf")
    return complete_upload(
        upload_id=created["uploadId"],
        content_sha256=content_sha256,
        byte_size=len(file_bytes),
        owner=owner,
        sync_processing=sync_processing,
    )
