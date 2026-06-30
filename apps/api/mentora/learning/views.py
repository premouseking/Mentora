"""
学习模块 HTTP 视图。

@module mentora/learning/views
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter

from mentora.learning.services import get_history
from mentora.learning.services.mistakes import get_explanations, get_mistake_items


@extend_schema(
    summary="获取学习记录",
    description="按课程获取学习事件时间线，倒序排列。",
    parameters=[
        OpenApiParameter(name="courseId", type=str, description="课程 ID", required=True),
        OpenApiParameter(name="limit", type=int, description="返回条数，默认 50"),
    ],
    responses={200: {"description": "学习事件列表"}},
)
@api_view(["GET"])
def history_list(request):
    course_id = request.GET.get("courseId", "").strip()
    if not course_id:
        return Response({"error": "缺少 courseId 参数"}, status=400)

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

    items = get_mistake_items(course_id)
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
