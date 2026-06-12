from django.http import JsonResponse
from django.urls import path


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    path("api/health/", health, name="health"),
]

