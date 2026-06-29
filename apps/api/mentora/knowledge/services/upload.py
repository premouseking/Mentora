"""
上传会话创建与完成校验。

约定：
- complete 时创建 Source + SourceVersion，触发解析入库
- uploadId 由客户端在 create 时提供或服务器生成

@module mentora/knowledge/services/upload
"""

import uuid

from django.conf import settings
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


DEV_OWNER_ID = settings.DEV_OWNER_ID


def _resolve_owner_id(owner_id: str | None) -> str:
    if owner_id:
        return owner_id
    if settings.DEBUG:
        return DEV_OWNER_ID
    raise ValueError("缺少 owner_id")


def create_upload_session(
    owner_id: str | None = None,
    upload_id: str | None = None,
    byte_size: int | None = None,
    filename: str = "original.pdf",
    media_type: str = "application/pdf",
) -> dict:
    """创建上传会话并返回预签名 PUT URL。"""
    owner_id = _resolve_owner_id(owner_id)
    storage = ObjectStorageService()
    storage.ensure_bucket()

    session_id = upload_id or str(uuid.uuid4())
    object_key = storage.upload_key_for_session(session_id, filename)

    session, _ = UploadSession.objects.update_or_create(
        id=session_id,
        defaults={
            "owner_id": owner_id,
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


def complete_upload(
    upload_id: str,
    content_sha256: str,
    byte_size: int,
    owner_id: str | None = None,
    sync_processing: bool = True,
) -> dict:
    """校验上传对象并创建 SourceVersion，可选同步解析。"""
    owner_id = _resolve_owner_id(owner_id)
    storage = ObjectStorageService()

    try:
        session = UploadSession.objects.get(id=upload_id, owner_id=owner_id)
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

    with transaction.atomic():
        source = Source.objects.create(
            owner_id=owner_id,
            display_title=session.original_filename or "未命名资料",
            status=SourceStatus.ACTIVE,
        )
        source_version = SourceVersion.objects.create(
            source=source,
            version_number=1,
            content_sha256=content_sha256,
            object_key=session.object_key,
            media_type=session.media_type,
            byte_size=byte_size,
            original_filename=session.original_filename,
            processing_status=ProcessingStatus.PENDING,
        )
        source.latest_version = source_version
        source.save(update_fields=["latest_version"])

        session.status = UploadSessionStatus.COMPLETED
        session.content_sha256 = content_sha256
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
    owner_id: str | None = None,
    sync_processing: bool = True,
) -> dict:
    """
    直接上传文件到对象存储并走完 complete 流程（seed/smoke 用，不经 HTTP PUT）。
    """
    owner_id = _resolve_owner_id(owner_id)
    created = create_upload_session(
        owner_id=owner_id,
        byte_size=len(file_bytes),
        filename=filename,
    )
    storage = ObjectStorageService()
    storage.put_object(created["objectKey"], file_bytes, content_type="application/pdf")
    return complete_upload(
        upload_id=created["uploadId"],
        content_sha256=content_sha256,
        byte_size=len(file_bytes),
        owner_id=owner_id,
        sync_processing=sync_processing,
    )
