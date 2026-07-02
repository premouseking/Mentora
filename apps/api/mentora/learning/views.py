"""
学习模块 HTTP 视图。

@module mentora/learning/views
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter

from mentora.learning.services import complete_task, get_history, get_task_detail
from mentora.learning.services.mistakes import archive_mistake, get_explanations, get_mistake_items, unarchive_mistake


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

    return Response(get_history(course_id, limit=limit))


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

    items = get_explanations(course_id)
    return Response({"items": items})


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
    if task is None:
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
    return Response(archive_mistake(course_id, str(item_id)))


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
    return Response(unarchive_mistake(course_id, str(item_id)))
