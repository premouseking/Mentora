"""
rate_limit 装饰器测试（滑动窗口限流）。

使用 DummyCache 避免依赖 Redis。
"""

from unittest.mock import MagicMock

import pytest
from django.test.utils import override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from mentora.agent_runtime.decorators import rate_limit


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
)
def test_rate_limit_allows_within_window():
    """窗口内不超过 max_attempts 时正常通过。"""

    @rate_limit("test", max_attempts=3, window_seconds=60)
    def dummy_view(request):
        return Response({"ok": True})

    factory = APIRequestFactory()
    request = factory.get("/test", REMOTE_ADDR="192.168.1.1")

    for _ in range(3):
        resp = dummy_view(request)
        assert resp.status_code == 200


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
)
def test_rate_limit_blocks_when_exceeded():
    """超过 max_attempts 时返回 429 + retry_after。"""

    @rate_limit("test_blocks", max_attempts=2, window_seconds=60)
    def dummy_view(request):
        return Response({"ok": True})

    factory = APIRequestFactory()
    request = factory.get("/test", REMOTE_ADDR="10.0.0.1")

    # 前 2 次通过
    for _ in range(2):
        resp = dummy_view(request)
        assert resp.status_code == 200

    # 第 3 次被限流
    resp = dummy_view(request)
    assert resp.status_code == 429
    data = resp.data
    assert "retry_after" in data
    assert data["retry_after"] >= 1


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
)
def test_rate_limit_ip_isolation():
    """不同 IP 的限流互不影响。"""

    @rate_limit("iso", max_attempts=1, window_seconds=60)
    def dummy_view(request):
        return Response({"ok": True})

    factory = APIRequestFactory()

    # IP A 用完配额
    req_a = factory.get("/test", REMOTE_ADDR="192.168.1.1")
    assert dummy_view(req_a).status_code == 200
    assert dummy_view(req_a).status_code == 429

    # IP B 不受影响
    req_b = factory.get("/test", REMOTE_ADDR="192.168.1.2")
    assert dummy_view(req_b).status_code == 200
