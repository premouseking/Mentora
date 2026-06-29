"""Parsing API environment boundary tests."""

from django.test import RequestFactory, override_settings

from mentora.parsing import views


@override_settings(DEBUG=False)
def test_benchmark_is_disabled_outside_debug():
    response = views.get_benchmark(RequestFactory().get("/api/parsing/benchmark"))

    assert response.status_code == 404
    assert response.data == {"error": "Benchmark 仅允许在开发环境运行"}
