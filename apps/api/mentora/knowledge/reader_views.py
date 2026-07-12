"""
LightRead-like Resource / Reader API。

@module mentora/knowledge/reader_views
"""

from __future__ import annotations

import json

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from mentora.knowledge.layout_converter import (
    blocks_to_outline,
    build_evidence_element_map,
    bundle_to_blocks,
    bundle_to_page_infos,
)
from mentora.knowledge.models import Source, SourceVersion
from mentora.knowledge.reader_contract import PdfReaderDocument, ResourceItem, ResourceMeta
from mentora.parsing.contract import serialize_parsed_bundle
from mentora.parsing.schemas import ParsedBundle


def _media_type_to_resource_type(media_type: str, filename: str) -> str:
    lower = (filename or "").lower()
    if media_type == "application/pdf" or lower.endswith(".pdf"):
        return "pdf"
    if "word" in media_type or lower.endswith(".docx"):
        return "docx"
    if "presentation" in media_type or lower.endswith(".pptx"):
        return "pptx"
    if media_type.startswith("image/"):
        return "image"
    return "file"


def _open_method(media_type: str, filename: str) -> str:
    rtype = _media_type_to_resource_type(media_type, filename)
    if rtype == "pdf":
        return "pdf"
    if rtype in ("docx", "pptx"):
        return "markdown"
    if rtype == "image":
        return "image"
    return "file"


def _version_page_count(version: SourceVersion) -> int:
    from django.db.models import Max
    from mentora.retrieval.models import EvidenceUnit

    agg = EvidenceUnit.objects.filter(source_version_id=str(version.id)).aggregate(
        max_page=Max("page_number"),
    )
    max_page = agg.get("max_page")
    if max_page:
        return int(max_page)
    return 0


def _source_version_to_resource(version: SourceVersion) -> ResourceItem:
    source = version.source
    bundle_pages = _version_page_count(version)

    return ResourceItem(
        resource_id=str(version.id),
        resource_name=source.display_title or version.original_filename or "未命名",
        resource_type=_media_type_to_resource_type(version.media_type, version.original_filename),
        open_method=_open_method(version.media_type, version.original_filename),
        pages=bundle_pages,
        file_size=version.byte_size,
        processing_status=version.processing_status,
        updated_at=version.created_at.isoformat() if hasattr(version, "created_at") and version.created_at else None,
        meta=ResourceMeta(
            filename=version.original_filename,
            media_type=version.media_type,
            byte_size=version.byte_size,
            source_id=str(source.id),
            parser_name=version.parser_name,
            parser_version=version.parser_version,
        ),
    )


def _load_bundle(version: SourceVersion) -> ParsedBundle | None:
    if not version.artifact_ref:
        return None
    try:
        from mentora.common.storage import ObjectStorageService

        raw = ObjectStorageService().get_object_bytes(version.artifact_ref)
        data = json.loads(raw.decode("utf-8"))
        normalized = serialize_parsed_bundle(data)
        if normalized is None:
            return None
        return ParsedBundle.model_validate(normalized)
    except Exception:
        return None


@api_view(["GET"])
def list_resources(request):
    qs = Source.objects.filter(owner=request.user).select_related("latest_version").order_by("-created_at")
    items = []
    for source in qs:
        latest = source.latest_version
        if latest is None:
            continue
        items.append(_source_version_to_resource(latest).model_dump(mode="json"))
    return Response({"items": items, "count": len(items)})


@api_view(["GET"])
def resource_info(request, resource_id):
    try:
        version = SourceVersion.objects.select_related("source").get(
            id=resource_id, source__owner=request.user,
        )
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)
    return Response(_source_version_to_resource(version).model_dump(mode="json"))


def _build_reader_document(version: SourceVersion, *, include_blocks: bool = True, pages_filter: set[int] | None = None):
    bundle = _load_bundle(version)
    if bundle is None:
        return None, Response({"error": "资料尚未解析完成"}, status=404)

    from mentora.retrieval.models import EvidenceUnit

    evidence_rows = list(
        EvidenceUnit.objects.filter(source_version_id=str(version.id)).order_by("page_number")
    )
    evidence_map = build_evidence_element_map(evidence_rows)

    blocks = bundle_to_blocks(bundle, evidence_map)
    if pages_filter is not None:
        blocks = [block for block in blocks if block.page in pages_filter]

    pages = bundle_to_page_infos(bundle)
    outline = blocks_to_outline(blocks if include_blocks else bundle_to_blocks(bundle, evidence_map))

    pdf_url = f"/api/resources/{version.id}/pdf/"
    doc = PdfReaderDocument(
        resource=_source_version_to_resource(version),
        pdf_url=pdf_url,
        pages=pages,
        blocks=blocks if include_blocks else [],
        outline=outline,
        parsed_bundle_ref=version.artifact_ref,
        layout_ref=f"layout/{version.id}.json",
        source_version_id=str(version.id),
    )
    return doc, None


@api_view(["GET"])
def resource_reader_meta(request, resource_id):
    try:
        version = SourceVersion.objects.select_related("source").get(
            id=resource_id, source__owner=request.user,
        )
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)

    doc, error_response = _build_reader_document(version, include_blocks=False)
    if error_response is not None:
        return error_response
    return Response(doc.model_dump(mode="json"))


@api_view(["GET"])
def resource_reader_blocks(request, resource_id):
    try:
        version = SourceVersion.objects.select_related("source").get(
            id=resource_id, source__owner=request.user,
        )
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)

    pages_param = (request.GET.get("pages") or request.GET.get("page") or "").strip()
    pages_filter: set[int] | None = None
    if pages_param:
        pages_filter = {int(p) for p in pages_param.split(",") if p.strip().isdigit()}

    doc, error_response = _build_reader_document(version, include_blocks=True, pages_filter=pages_filter)
    if error_response is not None:
        return error_response
    return Response({"blocks": [block.model_dump(mode="json") for block in doc.blocks]})


@api_view(["GET"])
def resource_reader(request, resource_id):
    try:
        version = SourceVersion.objects.select_related("source").get(
            id=resource_id, source__owner=request.user,
        )
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)

    doc, error_response = _build_reader_document(version, include_blocks=True)
    if error_response is not None:
        return error_response
    return Response(doc.model_dump(mode="json"))


@api_view(["GET"])
def resource_pdf(request, resource_id):
    from mentora.knowledge.asset_streaming import stream_source_version_asset
    from mentora.knowledge.models import SourceVersion

    try:
        version = SourceVersion.objects.get(id=resource_id, source__owner=request.user)
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)

    return stream_source_version_asset(
        version,
        str(resource_id),
        kind="original",
        request=request,
    )


@api_view(["GET"])
def resource_page_thumbnails(request, resource_id):
    """返回页元数据；缩略图由前端 pdf.js 渲染。"""
    try:
        version = SourceVersion.objects.get(id=resource_id, source__owner=request.user)
    except SourceVersion.DoesNotExist:
        return Response({"error": "资源不存在"}, status=404)

    bundle = _load_bundle(version)
    if bundle is None:
        return Response({"pages": []})

    pages_param = (request.GET.get("pages") or "").strip()
    wanted: set[int] | None = None
    if pages_param:
        wanted = {int(p) for p in pages_param.split(",") if p.strip().isdigit()}

    pages = []
    for info in bundle_to_page_infos(bundle):
        if wanted is not None and info.page not in wanted:
            continue
        pages.append(
            {
                "page": info.page,
                "width": info.width,
                "height": info.height,
                "thumbnail_url": None,
            }
        )
    return Response({"pages": pages})
