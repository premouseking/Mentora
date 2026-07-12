"""
学习模块 HTTP 视图。

@module mentora/learning/views
"""

import json

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from mentora.learning.services import get_history
from mentora.learning.services.explanations import (
    commit_preview,
    delete_explanation_doc,
    generate_preview,
    get_explanation_doc,
    update_explanation_doc,
)
from mentora.learning.services.mistakes import get_explanations, get_mistake_items


def _parse_json_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return {}


@extend_schema(
    summary="获取学习记录",
    description="获取学习事件时间线，倒序排列。不传 courseId 时返回跨课程的全部记录。",
    parameters=[
        OpenApiParameter(name="courseId", type=str, description="课程 ID，选填，缺省返回全部课程"),
        OpenApiParameter(name="limit", type=int, description="返回条数，默认 50"),
    ],
    responses={200: {"description": "学习事件列表"}},
)
@api_view(["GET"])
def history_list(request):
    course_id = request.GET.get("courseId", "").strip()

    try:
        limit = int(request.GET.get("limit", 50))
    except ValueError:
        limit = 50

    items = get_history(course_id, limit=limit)
    return Response({"items": items, "count": len(items)})


@extend_schema(
    summary="错题汇总",
    description="返回课程中所有答错的题目，按错误次数降序排列。",
    tags=["学习记录"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
    responses={200: {"description": "错题列表"}, 400: {"description": "缺少 course_id"}},
)
@api_view(["GET"])
def mistake_list(request):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)

    items = get_mistake_items(course_id)
    return Response({"items": items, "count": len(items)})


@extend_schema(
    summary="AI 讲解列表",
    description="返回课程 AI 讲解文档列表，按更新时间倒序。",
    tags=["AI 讲解"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
    responses={200: {"description": "讲解列表"}, 400: {"description": "缺少 course_id"}},
)
@api_view(["GET"])
def explanation_list(request):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)

    items = get_explanations(course_id)
    return Response({"items": items, "count": len(items)})


@extend_schema(
    summary="AI 讲解详情 / 更新 / 删除",
    tags=["AI 讲解"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID"),
    ],
    responses={
        200: {"description": "详情或更新成功"},
        204: {"description": "已删除"},
        404: {"description": "不存在"},
    },
)
@api_view(["GET", "PATCH", "DELETE"])
def explanation_doc(request, doc_id):
    if request.method == "GET":
        course_id = request.GET.get("course_id", "").strip()
        detail = get_explanation_doc(str(doc_id), course_id or None)
        if detail is None:
            return Response({"error": "讲解文件不存在"}, status=404)
        return Response(detail)

    body = _parse_json_body(request)

    if request.method == "DELETE":
        course_id = (
            request.GET.get("course_id", "").strip()
            or str(body.get("course_id") or "").strip()
        )
        if not course_id:
            return Response({"error": "缺少 course_id"}, status=400)
        try:
            delete_explanation_doc(str(doc_id), course_id)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)
        return Response(status=204)

    course_id = str(body.get("course_id") or request.GET.get("course_id") or "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id"}, status=400)

    title = body.get("title")
    detail_field = body.get("detail")
    keywords = body.get("keywords") if isinstance(body.get("keywords"), list) else None
    doc_type = body.get("doc_type")

    try:
        updated = update_explanation_doc(
            str(doc_id),
            course_id,
            title=str(title).strip() if title is not None else None,
            detail=str(detail_field) if detail_field is not None else None,
            keywords=[str(k) for k in keywords] if keywords is not None else None,
            doc_type=str(doc_type).strip() if doc_type is not None else None,
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    return Response(updated)


@extend_schema(
    summary="预览对话归档到 AI 讲解",
    tags=["AI 讲解"],
    responses={200: {"description": "预览结果"}, 503: {"description": "LLM 未配置"}},
)
@api_view(["POST"])
def explanation_preview(request):
    if not settings.LLM_API_KEY:
        return Response({"error": "LLM_API_KEY 未配置"}, status=503)

    body = _parse_json_body(request)
    course_id = str(body.get("course_id") or "").strip()
    user_message = str(body.get("user_message") or "").strip()
    assistant_message = str(body.get("assistant_message") or "").strip()
    citations = body.get("citations") if isinstance(body.get("citations"), list) else []

    if not course_id:
        return Response({"error": "缺少 course_id"}, status=400)
    if not user_message or not assistant_message:
        return Response({"error": "缺少对话内容"}, status=400)
    if len(assistant_message) < 20:
        return Response({"error": "回答过短，无法生成有效摘要"}, status=400)

    try:
        preview = generate_preview(
            resource_id=course_id,
            user_message=user_message,
            assistant_message=assistant_message,
            citations=citations,
        )
    except RuntimeError as exc:
        return Response({"error": str(exc)}, status=503)
    except Exception as exc:
        return Response({"error": f"生成预览失败: {exc}"}, status=502)

    return Response(preview)


@extend_schema(
    summary="确认写入 AI 讲解",
    tags=["AI 讲解"],
    responses={200: {"description": "写入成功"}, 400: {"description": "预览无效"}},
)
@api_view(["POST"])
def explanation_commit(request):
    body = _parse_json_body(request)
    preview_id = str(body.get("preview_id") or "").strip()
    course_id = str(body.get("course_id") or "").strip()

    if not preview_id or not course_id:
        return Response({"error": "缺少 preview_id 或 course_id"}, status=400)

    try:
        result = commit_preview(preview_id, course_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    return Response(result)
