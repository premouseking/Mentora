from __future__ import annotations

from django.db.models import Prefetch
from rest_framework.decorators import api_view
from rest_framework.response import Response

from mentora.model_gateway.ledger import aggregate_usage
from mentora.model_gateway.models import ModelAttempt, ModelRequest


def _parse_int(value: str | None, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _message_preview(messages: list[dict]) -> list[dict]:
    previews = []
    for item in messages[-6:]:
        content = item.get("content")
        previews.append(
            {
                "role": item.get("role"),
                "content_preview": content[:240] if isinstance(content, str) else None,
            }
        )
    return previews


def _attempt_payload(attempt: ModelAttempt | None) -> dict | None:
    if attempt is None:
        return None
    return {
        "id": str(attempt.id),
        "attempt_number": attempt.attempt_number,
        "provider_name": attempt.provider_name,
        "model_name": attempt.model_name,
        "success": attempt.success,
        "usage_json": attempt.usage_json,
        "latency_ms": attempt.latency_ms,
        "error_code": attempt.error_code,
        "error_message": attempt.error_message,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


@api_view(["GET"])
def model_request_list(request):
    limit = _parse_int(request.GET.get("limit"), 50, minimum=1, maximum=200)
    offset = _parse_int(request.GET.get("offset"), 0, minimum=0, maximum=10_000)
    include_messages = request.GET.get("includeMessages", "").lower() == "true"
    task_type = request.GET.get("taskType", "").strip()
    success_filter = request.GET.get("success", "").strip().lower()

    qs = ModelRequest.objects.prefetch_related(
        Prefetch("attempts", queryset=ModelAttempt.objects.order_by("-created_at"))
    ).order_by("-created_at")
    if task_type:
        qs = qs.filter(task_type=task_type)
    if success_filter in {"true", "false"}:
        qs = qs.filter(attempts__success=(success_filter == "true")).distinct()

    total = qs.count()
    items = []
    for model_request in qs[offset : offset + limit]:
        attempts = list(model_request.attempts.all())
        latest_attempt = attempts[0] if attempts else None
        item = {
            "id": str(model_request.id),
            "task_type": model_request.task_type,
            "provider_name": model_request.provider_name,
            "output_schema_name": model_request.output_schema_name,
            "structured_output": model_request.structured_output,
            "attempt_count": len(attempts),
            "latest_attempt": _attempt_payload(latest_attempt),
            "created_at": model_request.created_at.isoformat()
            if model_request.created_at
            else None,
        }
        if include_messages:
            item["messages"] = model_request.messages_json
        else:
            item["message_preview"] = _message_preview(model_request.messages_json or [])
        items.append(item)

    return Response({"total": total, "limit": limit, "offset": offset, "items": items})


@api_view(["GET"])
def model_usage_summary(request):
    days = _parse_int(request.GET.get("days"), 1, minimum=1, maximum=90)
    task_type = request.GET.get("taskType", "").strip() or None
    provider = request.GET.get("provider", "").strip() or None
    return Response(aggregate_usage(days=days, task_type=task_type, provider=provider))
