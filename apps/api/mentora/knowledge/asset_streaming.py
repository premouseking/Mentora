"""资料版本对象流式读取，供 library asset 与 reader PDF 复用。"""

from __future__ import annotations

import re

from django.http import HttpResponse
from rest_framework.response import Response

from mentora.common.storage import ObjectStorageError, ObjectStorageService

_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

_ORIGINAL_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "mp4": "video/mp4",
    "mp3": "audio/mpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")


def resolve_asset_content_type(key: str, fallback: str = "application/octet-stream") -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return _IMAGE_CONTENT_TYPES.get(ext) or _ORIGINAL_CONTENT_TYPES.get(ext) or fallback


def parse_range_header(range_header: str, total_size: int) -> tuple[int, int] | None:
    """解析 RFC 7233 Range 头，返回 inclusive start/end。"""
    match = _RANGE_PATTERN.fullmatch(range_header.strip())
    if not match or total_size <= 0:
        return None

    start_raw, end_raw = match.groups()
    if start_raw and end_raw:
        start = int(start_raw)
        end = int(end_raw)
    elif start_raw:
        start = int(start_raw)
        end = total_size - 1
    elif end_raw:
        suffix = int(end_raw)
        if suffix <= 0:
            return None
        start = max(total_size - suffix, 0)
        end = total_size - 1
    else:
        return None

    if start < 0 or end < start or start >= total_size:
        return None
    end = min(end, total_size - 1)
    return start, end


def stream_source_version_asset(
    version,
    source_version_id: str,
    *,
    kind: str = "",
    key: str = "",
    request=None,
):
    kind = (kind or "").strip().lower()
    key = (key or "").strip()

    if kind == "original":
        key = version.object_key
        if not key or ".." in key or key.startswith("/") or "\\" in key:
            return Response({"error": "无效的对象键"}, status=400)
        if not key.startswith("uploads/"):
            return Response({"error": "无效的对象键"}, status=400)
        content_type = version.media_type or resolve_asset_content_type(key)
    else:
        if not key:
            return Response({"error": "缺少 key 参数"}, status=400)
        prefix = f"images/{source_version_id}/"
        if not key.startswith(prefix) or ".." in key or key.startswith("/") or "\\" in key:
            return Response({"error": "无效的对象键"}, status=400)
        content_type = resolve_asset_content_type(key)

    storage = ObjectStorageService()
    try:
        head = storage.head_object(key)
    except ObjectStorageError:
        return Response({"error": "对象不存在"}, status=404)

    total_size = int(head.get("ContentLength") or 0)
    range_header = ""
    if request is not None:
        range_header = (request.META.get("HTTP_RANGE") or "").strip()

    byte_range = parse_range_header(range_header, total_size) if range_header else None
    try:
        if byte_range is None:
            data = storage.get_object_bytes(key)
            response = HttpResponse(data, content_type=content_type)
            response["Accept-Ranges"] = "bytes"
            response["Content-Length"] = str(len(data))
            return response

        start, end = byte_range
        data = storage.get_object_bytes_range(key, start, end)
        response = HttpResponse(data, status=206, content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        response["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        response["Content-Length"] = str(len(data))
        return response
    except ObjectStorageError:
        return Response({"error": "对象不存在"}, status=404)
