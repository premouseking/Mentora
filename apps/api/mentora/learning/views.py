"""
学习模块 HTTP 视图。

@module mentora/learning/views
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter

from mentora.learning.services import get_history


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
