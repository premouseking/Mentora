"""检索和引用定位 API。"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema

from mentora.retrieval.locator import locate_evidence
from mentora.retrieval.search import search


@extend_schema(
    summary="混合检索",
    description="FTS + Trgm + Vector RRF 三路融合检索，支持 fts/grep 两种模式。通过 course_id 限定作用域。",
    parameters=[
        {"name": "q", "type": str, "required": True, "description": "查询文本"},
        {"name": "top_k", "type": int, "required": False, "description": "返回数量，默认 10"},
        {"name": "mode", "type": str, "required": False, "description": "fts（语义）或 grep（精确正则）"},
        {"name": "course_id", "type": str, "required": False, "description": "课程 ID，自动限定检索范围"},
    ],
)
def search_view(request):
    """
    GET /api/retrieval/search?q=<查询>&top_k=10&course_id=<课程ID>&mode=fts

    混合检索入口，返回 ranked EvidenceUnit 列表。
    作用域通过 course_id 从 courses 服务读取，不直接信任前端参数。
    """
    if request.method != "GET":
        return JsonResponse({"error": "仅支持 GET"}, status=405)

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "缺少 q 参数"}, status=400)

    try:
        top_k = int(request.GET.get("top_k", 10))
    except ValueError:
        top_k = 10

    mode = request.GET.get("mode", "fts")

    # 作用域：优先 course_id → 服务端读 courses scope
    source_version_ids = None
    course_id = request.GET.get("course_id", "").strip()
    if course_id:
        from mentora.courses.services import get_course_scope
        source_version_ids = get_course_scope(course_id)

    result_set = search(
        query, top_k=top_k,
        mode=mode,
        source_version_ids=source_version_ids,
    )

    return JsonResponse(result_set.to_dict())


@extend_schema(
    summary="证据引用定位",
    description="返回 EvidenceUnit 的页码、坐标与同页上下文。",
)
def locate_view(request, evidence_id: str):
    """
    GET /api/retrieval/evidence/<uuid>/location

    返回指定 EvidenceUnit 的引用定位信息。
    """
    if request.method != "GET":
        return JsonResponse({"error": "仅支持 GET"}, status=405)

    location = locate_evidence(evidence_id)
    if location is None:
        return JsonResponse({"error": "EvidenceUnit 不存在"}, status=404)

    return JsonResponse(location.to_dict())
