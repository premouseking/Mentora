"""
学习模块 HTTP 视图。

@module mentora/learning/views
"""

import json

from django.conf import settings

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter

from mentora.learning.services import complete_task, get_history, get_task_detail
from mentora.learning.services.explanations import (
    commit_preview,
    delete_explanation_doc,
    generate_preview,
    get_explanation_doc,
    update_explanation_doc,
)
from mentora.learning.services.mistakes import archive_mistake, get_explanations, get_mistake_items, unarchive_mistake


def _parse_json_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return {}


def _user_owns_course(request, course_id: str) -> bool:
    from mentora.courses.models import Course

    return Course.objects.filter(id=course_id, owner=request.user).exists()


@extend_schema(
    summary="获取学习记录",
    description="按课程获取学习事件时间线，倒序排列。",
    parameters=[
        OpenApiParameter(name="courseId", type=str, description="课程 ID（Course.id 或建课 session_id），省略则返回全部", required=False),
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

    if course_id:
        from mentora.courses.models import Course
        if not Course.objects.filter(id=course_id, owner=request.user).exists():
            return Response({"error": "课程不存在"}, status=404)
    return Response(get_history(course_id, limit=limit, owner=request.user))


@extend_schema(
    summary="错题汇总",
    description="返回课程中所有答错的题目，按错误次数降序排列。包含题干、选项、正确答案、解析及来源链接。",
    tags=["学习记录"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
    responses={
        200: {"description": "错题列表"},
        400: {"description": "缺少 course_id"},
    },
)
@api_view(["GET"])
def mistake_list(request):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)
    from mentora.courses.models import Course
    if not Course.objects.filter(id=course_id, owner=request.user).exists():
        return Response({"error": "课程不存在"}, status=404)

    include_archived = request.GET.get("include_archived", "").lower() in ("1", "true", "yes")
    items = get_mistake_items(course_id, include_archived=include_archived)
    return Response({"items": items})


@extend_schema(
    summary="AI 讲解列表",
    description="返回课程中已完成的 AI 讲解记录，按时间倒序排列。",
    tags=["学习记录"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
    responses={
        200: {"description": "讲解列表"},
        400: {"description": "缺少 course_id"},
    },
)
@api_view(["GET"])
def explanation_list(request):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)
    from mentora.courses.models import Course
    if not Course.objects.filter(id=course_id, owner=request.user).exists():
        return Response({"error": "课程不存在"}, status=404)

    items = get_explanations(course_id)
    return Response({"items": items})


@api_view(["GET", "PATCH", "DELETE"])
def explanation_doc(request, doc_id):
    body = _parse_json_body(request) if request.method != "GET" else {}
    course_id = str(
        request.GET.get("course_id") or body.get("course_id") or ""
    ).strip()
    if not course_id:
        return Response({"error": "缺少 course_id"}, status=400)
    if not _user_owns_course(request, course_id):
        return Response({"error": "课程不存在"}, status=404)

    if request.method == "GET":
        detail = get_explanation_doc(str(doc_id), course_id)
        if detail is None:
            return Response({"error": "讲解文件不存在"}, status=404)
        return Response(detail)

    if request.method == "DELETE":
        try:
            delete_explanation_doc(str(doc_id), course_id)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)
        return Response(status=204)

    keywords = body.get("keywords") if isinstance(body.get("keywords"), list) else None
    try:
        updated = update_explanation_doc(
            str(doc_id),
            course_id,
            title=str(body["title"]).strip() if "title" in body else None,
            detail=str(body["detail"]) if "detail" in body else None,
            keywords=[str(keyword) for keyword in keywords] if keywords is not None else None,
            doc_type=str(body["doc_type"]).strip() if "doc_type" in body else None,
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)
    return Response(updated)


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
    if not _user_owns_course(request, course_id):
        return Response({"error": "课程不存在"}, status=404)
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


@api_view(["POST"])
def explanation_commit(request):
    body = _parse_json_body(request)
    preview_id = str(body.get("preview_id") or "").strip()
    course_id = str(body.get("course_id") or "").strip()
    if not preview_id or not course_id:
        return Response({"error": "缺少 preview_id 或 course_id"}, status=400)
    if not _user_owns_course(request, course_id):
        return Response({"error": "课程不存在"}, status=404)
    try:
        result = commit_preview(preview_id, course_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(result)


@extend_schema(
    summary="学习任务详情",
    description="返回学习任务的完整内容，包含按序渲染的内容块（标题/段落/引用/图解/提示/测验）和来源资料。",
    tags=["学习记录"],
    responses={
        200: {"description": "任务详情"},
        404: {"description": "任务不存在"},
    },
)
@api_view(["GET"])
def task_detail(request, task_id):
    """GET /api/learning/tasks/<task_id>/"""
    from mentora.learning.models import LearningTask
    if not LearningTask.objects.filter(
        id=task_id, revision__learning_plan__owner=request.user,
    ).exists():
        return Response({"error": "任务不存在"}, status=404)
    detail = get_task_detail(task_id)
    if detail is None:
        return Response({"error": "任务不存在"}, status=404)
    return Response(detail)


@extend_schema(
    summary="标记学习任务完成",
    tags=["学习记录"],
    responses={
        200: {"description": "任务已标记完成"},
        404: {"description": "任务不存在"},
    },
)
@api_view(["POST"])
def task_complete(request, task_id):
    """POST /api/learning/tasks/<task_id>/complete/"""
    from mentora.learning.services.task_sources import resolve_learning_task

    task = resolve_learning_task(str(task_id))
    if task is None or task.revision.learning_plan.owner_id != request.user.id:
        return Response({"error": "任务不存在"}, status=404)
    result = complete_task(str(task.id))
    return Response(result)


@extend_schema(
    summary="归档错题",
    description="将错题从默认错题集隐藏，不影响历史作答记录。",
    tags=["学习记录"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
)
@api_view(["PATCH"])
def mistake_archive(request, item_id):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)
    from mentora.courses.models import Course
    if not Course.objects.filter(id=course_id, owner=request.user).exists():
        return Response({"error": "课程不存在"}, status=404)
    return Response(archive_mistake(course_id, str(item_id), owner=request.user))


@extend_schema(
    summary="取消归档错题",
    tags=["学习记录"],
    parameters=[
        OpenApiParameter(name="course_id", type=str, description="课程 ID", required=True),
    ],
)
@api_view(["PATCH"])
def mistake_unarchive(request, item_id):
    course_id = request.GET.get("course_id", "").strip()
    if not course_id:
        return Response({"error": "缺少 course_id 参数"}, status=400)
    from mentora.courses.models import Course
    if not Course.objects.filter(id=course_id, owner=request.user).exists():
        return Response({"error": "课程不存在"}, status=404)
    return Response(unarchive_mistake(course_id, str(item_id), owner=request.user))
