"""
请求频率限流装饰器（参考 LightRead rate_limit.py 滑动窗口模式）。

@module mentora/agent_runtime/decorators
"""

import time
from functools import wraps

from django.core.cache import cache
from rest_framework.response import Response


def rate_limit(key_prefix: str, max_attempts: int, window_seconds: int):
    """滑动窗口限流装饰器。

    以 IP + key_prefix 为粒度，在 window_seconds 内最多允许 max_attempts 次请求。
    超限返回 429，含 retry_after 字段。

    使用方式：
        @rate_limit("chat", 10, 60)
        @api_view(["POST"])
        def chat_api(request): ...
    """

    def decorator(view_fn):
        @wraps(view_fn)
        def wrapper(request, *args, **kwargs):
            ip = _client_ip(request)
            cache_key = f"rate_limit:{key_prefix}:{ip}"

            now = time.time()
            timestamps: list[float] = cache.get(cache_key) or []

            # 过滤窗口外的过期时间戳
            cutoff = now - window_seconds
            valid = [t for t in timestamps if t > cutoff]

            if len(valid) >= max_attempts:
                retry_after = int(valid[0] - cutoff) if valid else window_seconds
                return Response(
                    {"error": "请求过于频繁，请稍后重试", "retry_after": max(retry_after, 1)},
                    status=429,
                )

            valid.append(now)
            cache.set(cache_key, valid, timeout=window_seconds)
            return view_fn(request, *args, **kwargs)

        return wrapper

    return decorator


def _client_ip(request) -> str:
    """提取客户端 IP（优先取 X-Forwarded-For）。"""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
