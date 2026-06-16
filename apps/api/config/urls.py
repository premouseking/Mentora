from django.http import JsonResponse
from django.urls import path

from mentora.parsing.views import get_benchmark, preview_parse
from mentora.retrieval.views import locate_view, search_view


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/parsing/preview", preview_parse, name="parsing-preview"),
    path("api/parsing/benchmark", get_benchmark, name="parsing-benchmark"),
    path("api/retrieval/search", search_view, name="retrieval-search"),
    path("api/retrieval/evidence/<uuid:evidence_id>/location", locate_view, name="retrieval-locate"),
]
