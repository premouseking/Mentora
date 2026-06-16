from django.http import JsonResponse
from django.urls import path

from mentora.knowledge.views import list_sources, upload_complete, upload_create
from mentora.parsing.views import get_benchmark, preview_parse


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/uploads/", upload_create, name="upload-create"),
    path("api/uploads/complete/", upload_complete, name="upload-complete"),
    path("api/library/sources/", list_sources, name="library-sources"),
    path("api/parsing/preview", preview_parse, name="parsing-preview"),
    path("api/parsing/benchmark", get_benchmark, name="parsing-benchmark"),
]
