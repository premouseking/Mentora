"""知识库 HTTP 视图。"""

import json
import uuid

from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from mentora.knowledge.models import CourseSource, LibraryFolder, Source, SourceStatus
from mentora.knowledge.services.upload import (
    DEV_OWNER_ID,
    complete_upload,
    create_upload_session,
)


def _parse_json_body(request) -> dict:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _parse_optional_uuid(value: object, field_name: str) -> tuple[str | None, Response | None]:
    if value in (None, ""):
        return None, None
    try:
        return str(uuid.UUID(str(value))), None
    except (TypeError, ValueError):
        return None, Response({"error": f"{field_name} 格式无效"}, status=400)


def _resolve_owner_id(value: object | None) -> tuple[str | None, Response | None]:
    owner_id = str(value or "").strip()
    if owner_id:
        return owner_id, None
    if settings.DEBUG:
        return DEV_OWNER_ID, None
    return None, Response({"error": "缺少 ownerId"}, status=400)


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

    owner_id, error_response = _resolve_owner_id(body.get("ownerId"))
    if error_response is not None:
        return error_response

    result = create_upload_session(
        owner_id=owner_id,
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

    owner_id, error_response = _resolve_owner_id(body.get("ownerId"))
    if error_response is not None:
        return error_response

    try:
        result = complete_upload(
            upload_id=str(upload_id),
            content_sha256=str(sha256),
            byte_size=int(size),
            owner_id=owner_id,
            sync_processing=body.get("sync", True),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    # 写入学习记录
    from mentora.learning.services import write_history_event
    write_history_event(
        course_id="",
        event_type="source_added",
        title=f"上传资料：{result.get('original_filename', '') or '新资料'}",
        detail="资料解析完成。",
        result=f"{result.get('byte_size', 0)} bytes",
    )

    return Response(result)


@extend_schema(
    summary="列出资料库",
    description="按所有者列出全部资料，可选按课程或标签过滤。tags 参数逗号分隔，取交集。",
    parameters=[
        OpenApiParameter(name="ownerId", type=str, description="所有者 ID", required=False),
        OpenApiParameter(name="courseId", type=str, description="课程会话 ID，传入时仅返回已关联资料", required=False),
        OpenApiParameter(name="tags", type=str, description="逗号分隔的标签，取交集过滤", required=False),
        OpenApiParameter(name="status", type=str, description="过滤状态: active/archived", required=False),
        OpenApiParameter(name="q", type=str, description="搜索关键词，模糊匹配资料标题", required=False),
        OpenApiParameter(name="folderId", type=str, description="文件夹 ID，传入时仅返回该文件夹下的资料", required=False),
    ],
    responses={200: {"description": "资料列表"}},
)
@api_view(["GET"])
def list_sources(request):
    owner_id, error_response = _resolve_owner_id(request.GET.get("ownerId"))
    if error_response is not None:
        return error_response
    course_id = request.GET.get("courseId", "").strip()
    tags_filter = [t.strip() for t in request.GET.get("tags", "").split(",") if t.strip()]
    status_filter = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    folder_id, error_response = _parse_optional_uuid(request.GET.get("folderId", "").strip(), "folderId")
    if error_response is not None:
        return error_response

    qs = Source.objects.filter(owner_id=owner_id).select_related("latest_version")

    if folder_id:
        qs = qs.filter(folder_id=folder_id)

    if q:
        qs = qs.filter(display_title__icontains=q)

    if status_filter in ("active", "archived"):
        qs = qs.filter(status=status_filter)

    if course_id:
        # 优先读正式课程作用域，没有则回退到临时关联记录
        from mentora.courses.services import get_course_scope
        from mentora.courses.models import Course

        linked_version_ids = None
        try:
            course = Course.objects.get(id=course_id)
            linked_version_ids = get_course_scope(str(course.id))
            course_id = str(course.session_id)
        except Course.DoesNotExist:
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
    owner_id, error_response = _resolve_owner_id(request.GET.get("ownerId"))
    if error_response is not None:
        return error_response
    sources = Source.objects.filter(owner_id=owner_id).values_list("tags", flat=True)
    all_tags: set[str] = set()
    for tags in sources:
        if isinstance(tags, list):
            all_tags.update(tags)
    return Response({"tags": sorted(all_tags)})


@extend_schema(
    summary="归档资料",
    description="将资料状态设为 archived，保留历史回答可追溯。",
    responses={200: {"description": "归档成功"}, 404: {"description": "资料不存在"}},
)
@api_view(["PATCH"])
def source_archive(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)
    source.status = SourceStatus.ARCHIVED
    source.save(update_fields=["status"])
    return Response({"status": source.status})


@extend_schema(
    summary="取消归档",
    description="将资料恢复为 active 状态。",
    responses={200: {"description": "恢复成功"}, 404: {"description": "资料不存在"}},
)
@api_view(["PATCH"])
def source_unarchive(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)
    source.status = SourceStatus.ACTIVE
    source.save(update_fields=["status"])
    return Response({"status": source.status})


# ── Folder 管理 ──


@extend_schema(
    summary="创建文件夹",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "文件夹名称"},
                "parentId": {"type": "string", "description": "父文件夹 ID（可选）"},
                "ownerId": {"type": "string", "description": "所有者 ID"},
            },
            "required": ["name"],
        },
    },
    responses={201: {"description": "创建成功"}},
)
@api_view(["POST"])
def folder_create(request):
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)
    name = (body.get("name") or "").strip()
    if not name:
        return Response({"error": "缺少 name"}, status=400)
    owner_id, error_response = _resolve_owner_id(body.get("ownerId"))
    if error_response is not None:
        return error_response
    parent_id, error_response = _parse_optional_uuid(body.get("parentId"), "parentId")
    if error_response is not None:
        return error_response
    if parent_id and not LibraryFolder.objects.filter(id=parent_id, owner_id=owner_id).exists():
        return Response({"error": "父文件夹不存在"}, status=404)
    folder = LibraryFolder.objects.create(
        owner_id=owner_id,
        name=name,
        parent_id=parent_id,
    )
    return Response({"id": str(folder.id), "name": folder.name, "parentId": str(folder.parent_id) if folder.parent_id else None}, status=201)


@extend_schema(
    summary="列出文件夹",
    description="返回当前用户的文件夹列表，含子文件夹数和资料数。",
    parameters=[
        OpenApiParameter(name="ownerId", type=str, description="所有者 ID", required=False),
    ],
    responses={200: {"description": "文件夹列表"}},
)
@api_view(["GET"])
def folder_list(request):
    owner_id, error_response = _resolve_owner_id(request.GET.get("ownerId"))
    if error_response is not None:
        return error_response
    folders = LibraryFolder.objects.filter(owner_id=owner_id)
    items = []
    for f in folders:
        items.append({
            "id": str(f.id),
            "name": f.name,
            "parentId": str(f.parent_id) if f.parent_id else None,
            "childCount": f.children.count(),
            "sourceCount": f.sources.count(),
            "position": f.position,
        })
    return Response({"items": items, "count": len(items)})


@extend_schema(
    summary="重命名文件夹",
    request={
        "application/json": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "新名称"}},
            "required": ["name"],
        },
    },
    responses={200: {"description": "重命名成功"}, 404: {"description": "文件夹不存在"}},
)
@api_view(["PATCH"])
def folder_rename(request, folder_id):
    try:
        folder = LibraryFolder.objects.get(id=folder_id)
    except LibraryFolder.DoesNotExist:
        return Response({"error": "文件夹不存在"}, status=404)
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)
    name = (body.get("name") or "").strip()
    if not name:
        return Response({"error": "缺少 name"}, status=400)
    folder.name = name
    folder.save(update_fields=["name"])
    return Response({"id": str(folder.id), "name": folder.name})


@extend_schema(
    summary="删除文件夹",
    description="只能删除空文件夹（无子文件夹且无资料）。",
    responses={200: {"description": "删除成功"}, 400: {"description": "文件夹非空"}, 404: {"description": "文件夹不存在"}},
)
@api_view(["DELETE"])
def folder_delete(request, folder_id):
    try:
        folder = LibraryFolder.objects.get(id=folder_id)
    except LibraryFolder.DoesNotExist:
        return Response({"error": "文件夹不存在"}, status=404)
    if folder.children.exists() or folder.sources.exists():
        return Response({"error": "文件夹非空，不能删除"}, status=400)
    folder.delete()
    return Response({"status": "deleted"})


@extend_schema(
    summary="移动资料",
    description="将资料移入/移出文件夹。folderId 传 null 可移出文件夹。",
    request={
        "application/json": {
            "type": "object",
            "properties": {"folderId": {"type": ["string", "null"], "description": "目标文件夹 ID，null 移出"}},
            "required": ["folderId"],
        },
    },
    responses={200: {"description": "移动成功"}, 404: {"description": "资料不存在"}},
)
@api_view(["PATCH"])
def source_move(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return Response({"error": "资料不存在"}, status=404)
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)
    folder_id, error_response = _parse_optional_uuid(body.get("folderId"), "folderId")
    if error_response is not None:
        return error_response
    if folder_id and not LibraryFolder.objects.filter(
        id=folder_id,
        owner_id=source.owner_id,
    ).exists():
        return Response({"error": "文件夹不存在"}, status=404)
    source.folder_id = folder_id if folder_id else None
    source.save(update_fields=["folder"])
    return Response({"id": str(source.id), "folderId": str(source.folder_id) if source.folder_id else None})


@extend_schema(
    summary="课程资料管理",
    description="GET 列出课程已关联资料；POST 批量替换关联。",
    methods=["GET", "POST"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "source_version_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "资料版本 ID 列表（POST 时使用）",
                },
            },
        },
    },
    responses={200: {"description": "资料列表或设置成功"}},
)
@api_view(["GET", "POST"])
def course_sources(request, session_id):
    from mentora.courses.models import CourseCreationSession
    from mentora.knowledge.models import SourceVersion

    try:
        session = CourseCreationSession.objects.get(id=session_id)
    except CourseCreationSession.DoesNotExist:
        return Response({"error": "课程创建会话不存在"}, status=404)

    if request.method == "GET":
        items = CourseSource.objects.filter(
            course_session_id=str(session_id),
        ).select_related("source_version__source").order_by("id")
        result = []
        for cs in items:
            sv = cs.source_version
            result.append({
                "id": str(sv.id),
                "sourceVersionId": str(sv.id),
                "sourceId": str(sv.source.id),
                "displayTitle": sv.source.display_title,
                "originalFilename": sv.original_filename,
                "byteSize": sv.byte_size,
                "processingStatus": sv.processing_status,
                "addedAt": cs.added_at.isoformat(),
            })
        return Response({"items": result, "count": len(result)})

    # POST
    try:
        body = _parse_json_body(request)
    except json.JSONDecodeError:
        return Response({"error": "无效 JSON"}, status=400)

    sv_ids = body.get("source_version_ids", [])
    if not isinstance(sv_ids, list):
        return Response({"error": "source_version_ids 必须是数组"}, status=400)

    normalized_ids = [str(sv_id) for sv_id in sv_ids if str(sv_id).strip()]
    found_ids = {
        str(sv_id)
        for sv_id in SourceVersion.objects.filter(
            id__in=normalized_ids,
        ).values_list("id", flat=True)
    }
    missing_ids = [sv_id for sv_id in normalized_ids if sv_id not in found_ids]
    if missing_ids:
        return Response({"error": "资料版本不存在", "missing": missing_ids}, status=400)
    # 清空旧关联
    CourseSource.objects.filter(course_session_id=str(session_id)).delete()
    # 写入新关联
    for sv_id in normalized_ids:
        CourseSource.objects.create(
            course_session_id=str(session_id),
            source_version_id=sv_id,
        )
    session.extra["source_version_ids"] = normalized_ids
    session.save(update_fields=["extra", "updated_at"])
    return Response({"count": len(normalized_ids), "source_version_ids": normalized_ids})
