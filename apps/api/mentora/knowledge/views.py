"""知识库 HTTP 视图。"""

import json
import uuid

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.knowledge.models import CourseSource, Source
from mentora.knowledge.services.upload import (
    DEV_OWNER_ID,
    complete_upload,
    create_upload_session,
)


def _parse_json_body(request) -> dict:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


@api_view(["POST"])
@extend_schema(summary="Upload Create")
def upload_create(request):
    """
    POST /api/uploads/

    创建上传会话，返回预签名 PUT URL。客户端应携带 uploadId 以便 complete 关联。
    """
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    upload_id = body.get("uploadId")
    if upload_id is not None:
        try:
            uuid.UUID(str(upload_id))
        except ValueError:
            return Response({"error": "uploadId 格式无效"}, status=400)

    result = create_upload_session(
        owner_id=body.get("ownerId", DEV_OWNER_ID),
        upload_id=str(upload_id) if upload_id else None,
        byte_size=body.get("size"),
        filename=body.get("filename", "original.pdf"),
        media_type=body.get("mediaType", "application/pdf"),
    )
    return Response(result)


@api_view(["POST"])
@extend_schema(summary="Upload Complete")
def upload_complete(request):
    """
    POST /api/uploads/complete/

    校验上传完成，创建 SourceVersion 并触发解析。
    """
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    upload_id = body.get("uploadId")
    sha256 = body.get("sha256")
    size = body.get("size")

    if not upload_id or not sha256 or size is None:
        return Response({"error": "缺少 uploadId、sha256 或 size"}, status=400)

    try:
        result = complete_upload(
            upload_id=str(upload_id),
            content_sha256=str(sha256),
            byte_size=int(size),
            owner_id=body.get("ownerId", DEV_OWNER_ID),
            sync_processing=body.get("sync", True),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    return Response(result)


@api_view(["GET"])
@extend_schema(summary="List Sources")
def list_sources(request):
    """GET /api/library/sources/?ownerId=&courseId= — 列出资料。

    courseId 可选：传入时仅返回已关联到该课程的资料。
    """
    owner_id = request.GET.get("ownerId", DEV_OWNER_ID)
    course_id = request.GET.get("courseId", "").strip()

    qs = Source.objects.filter(owner_id=owner_id).select_related("latest_version")

    if course_id:
        # 优先读正式课程作用域，没有则回退到临时关联记录
        from mentora.courses.services import get_course_scope
        from mentora.courses.models import Course

        linked_version_ids = None
        try:
            course = Course.objects.get(session_id=course_id)
            linked_version_ids = get_course_scope(str(course.id))
        except Course.DoesNotExist:
            pass

        if not linked_version_ids:
            linked_version_ids = list(
                CourseSource.objects.filter(
                    course_session_id=course_id,
                ).values_list("source_version_id", flat=True)
            )

        if linked_version_ids:
            qs = qs.filter(latest_version__id__in=linked_version_ids)

    items = []
    for source in qs.order_by("-created_at"):
        latest = source.latest_version
        items.append(
            {
                "id": str(source.id),
                "displayTitle": source.display_title,
                "status": source.status,
                "latestVersion": None if latest is None else {
                    "id": str(latest.id),
                    "versionNumber": latest.version_number,
                    "processingStatus": latest.processing_status,
                    "byteSize": latest.byte_size,
                    "originalFilename": latest.original_filename,
                },
            }
        )
    return Response({"items": items, "count": len(items)})


@api_view(["GET"])
@extend_schema(summary="Source Detail")
def source_detail(request, source_version_id):
    """GET /api/library/sources/<source_version_id>/ — 获取资料版本详情与解析正文。"""
    from mentora.common.storage import ObjectStorageError, ObjectStorageService
    from mentora.knowledge.models import SourceVersion

    try:
        version = SourceVersion.objects.select_related("source").get(id=source_version_id)
    except SourceVersion.DoesNotExist:
        return Response({"error": "资料版本不存在"}, status=404)

    bundle_data = None
    if version.artifact_ref:
        try:
            storage = ObjectStorageService()
            raw = storage.get_object_bytes(version.artifact_ref)
            bundle_data = json.loads(raw.decode("utf-8"))
        except (ObjectStorageError, json.JSONDecodeError):
            pass

    return Response({
        "source": {
            "id": str(version.source.id),
            "displayTitle": version.source.display_title,
            "status": version.source.status,
        },
        "version": {
            "id": str(version.id),
            "versionNumber": version.version_number,
            "processingStatus": version.processing_status,
            "byteSize": version.byte_size,
            "originalFilename": version.original_filename,
            "mediaType": version.media_type,
            "parserName": version.parser_name,
            "parserVersion": version.parser_version,
            "errorCode": version.error_code,
            "errorMessage": version.error_message,
        },
        "bundle": bundle_data,
    })


@api_view(["DELETE"])
@extend_schema(summary="Source Delete")
def source_delete(request, source_id):
    """DELETE /api/library/sources/<source_id>/ — 删除资料及关联的版本和解析数据。"""
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)

    source.delete()  # CASCADE: SourceVersion → UploadSession, ProcessingRun
    return Response({"status": "deleted"})


@api_view(["POST"])
@extend_schema(summary="Source Reparse")
def source_reparse(request, source_id):
    """POST /api/library/sources/<source_id>/reparse/ — 重新解析资料。"""
    from mentora.knowledge.models import ProcessingRun, ProcessingRunStatus, ProcessingStatus
    from mentora.knowledge.services.processing import run_processing_for_version

    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)

    version = source.latest_version
    if version is None:
        return Response({"error": "资料没有版本记录"}, status=400)

    # 清理旧解析数据
    ProcessingRun.objects.filter(source_version=version).delete()
    from mentora.retrieval.models import ChunkProjection, EvidenceUnit
    EvidenceUnit.objects.filter(source_version_id=str(version.id)).delete()
    ChunkProjection.objects.filter(source_version_id=str(version.id)).delete()

    # 重新触发解析（sync）
    version.processing_status = ProcessingStatus.PENDING
    version.save(update_fields=["processing_status"])
    result = run_processing_for_version(str(version.id), sync=True)

    return Response({
        "status": result.status,
        "processingStatus": version.processing_status,
    })
