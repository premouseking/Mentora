"""知识库 HTTP 视图。"""

import json
import uuid

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

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


@extend_schema(
    summary="创建上传会话",
    description="创建上传会话，返回对象存储键和上传 ID。客户端应携带 uploadId 以便 complete 关联。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "原始文件名"},
                "size": {"type": "integer", "description": "文件字节大小"},
                "mediaType": {"type": "string", "description": "MIME 类型，默认 application/pdf"},
                "ownerId": {"type": "string", "description": "所有者 ID"},
                "uploadId": {"type": "string", "description": "客户端生成的 UUID，用于幂等关联"},
            },
            "required": ["filename", "size"],
        },
    },
    responses={
        200: {"description": "上传会话创建成功"},
        400: {"description": "参数无效"},
    },
)
@api_view(["POST"])
def upload_create(request):
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


@extend_schema(
    summary="完成上传并触发解析",
    description="校验文件 SHA256 与大小，创建 Source/SourceVersion，触发异步解析管线。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "uploadId": {"type": "string", "description": "上传会话 UUID"},
                "sha256": {"type": "string", "description": "文件 SHA-256 哈希（十六进制）"},
                "size": {"type": "integer", "description": "实际文件字节大小"},
                "ownerId": {"type": "string", "description": "所有者 ID"},
                "sync": {"type": "boolean", "description": "是否同步等待解析完成，默认 true"},
            },
            "required": ["uploadId", "sha256", "size"],
        },
    },
    responses={
        200: {"description": "上传完成，解析已触发"},
        400: {"description": "校验失败（SHA256/大小不匹配）"},
    },
)
@api_view(["POST"])
def upload_complete(request):
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


@extend_schema(
    summary="列出资料库",
    description="按所有者列出全部资料，可选按课程或标签过滤。tags 参数逗号分隔，取交集。",
    parameters=[
        OpenApiParameter(name="ownerId", type=str, description="所有者 ID", required=False),
        OpenApiParameter(name="courseId", type=str, description="课程会话 ID，传入时仅返回已关联资料", required=False),
        OpenApiParameter(name="tags", type=str, description="逗号分隔的标签，取交集过滤", required=False),
    ],
    responses={200: {"description": "资料列表"}},
)
@api_view(["GET"])
def list_sources(request):
    owner_id = request.GET.get("ownerId", DEV_OWNER_ID)
    course_id = request.GET.get("courseId", "").strip()
    tags_filter = [t.strip() for t in request.GET.get("tags", "").split(",") if t.strip()]

    qs = Source.objects.filter(owner_id=owner_id).select_related("latest_version")

    if course_id:
        linked_version_ids = CourseSource.objects.filter(
            course_session_id=course_id,
        ).values_list("source_version_id", flat=True)
        qs = qs.filter(latest_version__id__in=linked_version_ids)

    items = []
    for source in qs.order_by("-created_at"):
        latest = source.latest_version
        # 标签过滤：交集匹配
        if tags_filter and not set(tags_filter).issubset(set(source.tags or [])):
            continue
        items.append(
            {
                "id": str(source.id),
                "displayTitle": source.display_title,
                "status": source.status,
                "tags": source.tags,
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


@extend_schema(
    summary="获取资料版本详情",
    description="返回资料元数据、版本信息与 ParsedBundle JSON（如已解析）。",
    responses={
        200: {"description": "资料详情"},
        404: {"description": "资料版本不存在"},
    },
)
@api_view(["GET"])
def source_detail(request, source_version_id):
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


@extend_schema(
    summary="删除资料",
    description="删除资料及 CASCADE 关联的版本、解析数据和检索证据。",
    responses={
        200: {"description": "删除成功"},
        404: {"description": "资料不存在"},
    },
)
@api_view(["DELETE"])
def source_delete(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)

    source.delete()  # CASCADE: SourceVersion → UploadSession, ProcessingRun
    return Response({"status": "deleted"})


@extend_schema(
    summary="重新解析资料",
    description="清理旧解析数据后重新触发同步解析管线。",
    responses={
        200: {"description": "重新解析完成"},
        400: {"description": "资料无版本记录"},
        404: {"description": "资料不存在"},
    },
)
@api_view(["POST"])
def source_reparse(request, source_id):
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


@extend_schema(
    summary="更新资料标签",
    description="替换指定资料的标签列表。",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
            },
            "required": ["tags"],
        },
    },
    responses={
        200: {"description": "更新成功"},
        404: {"description": "资料不存在"},
    },
)
@api_view(["PATCH"])
def source_update_tags(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)

    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    tags = body.get("tags", [])
    if not isinstance(tags, list):
        return Response({"error": "tags 必须为数组"}, status=400)

    source.tags = tags
    source.save(update_fields=["tags"])
    return Response({"tags": source.tags})


@extend_schema(
    summary="列出所有标签",
    description="返回当前用户所有资料中已使用的标签合集。",
    parameters=[
        OpenApiParameter(name="ownerId", type=str, description="所有者 ID", required=False),
    ],
    responses={200: {"description": "标签列表"}},
)
@api_view(["GET"])
def list_tags(request):
    owner_id = request.GET.get("ownerId", DEV_OWNER_ID)
    sources = Source.objects.filter(owner_id=owner_id).values_list("tags", flat=True)
    all_tags: set[str] = set()
    for tags in sources:
        if isinstance(tags, list):
            all_tags.update(tags)
    return Response({"tags": sorted(all_tags)})
