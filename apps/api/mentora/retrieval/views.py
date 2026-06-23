"""检索和引用定位 API。"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from mentora.retrieval.benchmark import _make_gold_corpus
from mentora.retrieval.locator import load_corpus as load_locator_corpus, locate_evidence
from mentora.retrieval.search import load_corpus as load_search_corpus, search


# 加载语料库（S2-LH-03 升级为 PG 原生查询）
_corpus, _ = _make_gold_corpus()
load_search_corpus(_corpus)
load_locator_corpus(_corpus)


def search_view(request):
    """
    GET /api/retrieval/search?q=<查询>&top_k=10

    混合检索入口，返回 ranked EvidenceUnit 列表。
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

    # 作用域过滤：逗号分隔的 source_version_id 列表
    sv_param = request.GET.get("source_version_ids", "")
    source_version_ids = [s.strip() for s in sv_param.split(",") if s.strip()] or None

    result_set = search(query, top_k=top_k, source_version_ids=source_version_ids)

    return JsonResponse(result_set.to_dict())


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
