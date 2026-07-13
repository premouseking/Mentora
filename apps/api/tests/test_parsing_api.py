"""Parsing API environment boundary tests."""

from types import SimpleNamespace

from django.test import RequestFactory, override_settings
from rest_framework.test import force_authenticate

from mentora.parsing import views


@override_settings(DEBUG=False)
def test_benchmark_is_disabled_outside_debug():
    request = RequestFactory().get("/api/parsing/benchmark")
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    response = views.get_benchmark(request)

    assert response.status_code == 404
    assert response.data == {"error": "Benchmark 仅允许在开发环境运行"}
