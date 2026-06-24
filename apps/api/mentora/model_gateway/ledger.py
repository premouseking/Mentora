"""
模型用量账本：聚合 Token 消耗、成功率、延迟与费用估算。

数据源：ModelRequest + ModelAttempt 审计记录
费用基于 model_name → 内置定价表，实际价格以 Provider 账单为准

@module mentora/model_gateway/ledger
"""

from datetime import datetime, timedelta, timezone

from django.db.models import Avg, Count, Q, Sum

from mentora.model_gateway.models import ModelAttempt, ModelRequest

# $/1M tokens (2026-06 参考价)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini":       {"input": 0.15, "output": 0.60},
    "gpt-4o":            {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini":      {"input": 0.40, "output": 1.60},
    "gpt-4.1":           {"input": 2.00, "output": 8.00},
    "deepseek-chat":     {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "doubao-1.5-pro":    {"input": 0.50, "output": 2.00},
}


def _estimate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name)
    if not pricing:
        return 0.0
    return (prompt_tokens / 1_000_000) * pricing["input"] + \
           (completion_tokens / 1_000_000) * pricing["output"]


def _build_group_rows(attempts, group_field: str) -> list[dict]:
    groups = {}
    for a in attempts:
        key = (a["request__task_type"] if group_field == "task_type"
               else a["provider_name"])
        if key not in groups:
            groups[key] = {"total": 0, "success": 0, "prompt_tokens": 0,
                           "completion_tokens": 0, "total_latency_ms": 0,
                           "cost": 0.0, "by_model": {}}
        g = groups[key]
        g["total"] += 1
        if a["success"]:
            g["success"] += 1
        usage = a["usage_json"] or {}
        p_tok = usage.get("prompt_tokens", 0) or 0
        c_tok = usage.get("completion_tokens", 0) or 0
        g["prompt_tokens"] += p_tok
        g["completion_tokens"] += c_tok
        g["total_latency_ms"] += a.get("latency_ms") or 0
        model = a["model_name"]
        if model not in g["by_model"]:
            g["by_model"][model] = {"count": 0, "prompt_tokens": 0, "completion_tokens": 0}
        g["by_model"][model]["count"] += 1
        g["by_model"][model]["prompt_tokens"] += p_tok
        g["by_model"][model]["completion_tokens"] += c_tok
        g["cost"] += _estimate_cost(model, p_tok, c_tok)

    rows = []
    for key, g in sorted(groups.items()):
        rows.append({
            "key": key,
            "requests": g["total"],
            "success_rate_pct": round(g["success"] / max(g["total"], 1) * 100, 1),
            "prompt_tokens": g["prompt_tokens"],
            "completion_tokens": g["completion_tokens"],
            "total_tokens": g["prompt_tokens"] + g["completion_tokens"],
            "avg_latency_ms": round(g["total_latency_ms"] / max(g["total"], 1)),
            "cost_approx": round(g["cost"], 4),
            "by_model": {
                m: {
                    "count": d["count"],
                    "tokens": d["prompt_tokens"] + d["completion_tokens"],
                }
                for m, d in g["by_model"].items()
            },
        })
    return rows


def aggregate_usage(
    days: int = 30,
    *,
    task_type: str | None = None,
    provider: str | None = None,
) -> dict:
    """
    汇总指定时间范围内的模型用量。

    返回：
    {
        "start_date", "end_date",
        "summary": {requests, success_rate_pct, total_tokens, cost_approx, avg_latency_ms},
        "by_task_type": [...],
        "by_provider": [...],
    }
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    attempts = ModelAttempt.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
    ).select_related("request").values(
        "request__task_type",
        "provider_name",
        "model_name",
        "success",
        "usage_json",
        "latency_ms",
    )

    if task_type:
        attempts = attempts.filter(request__task_type=task_type)
    if provider:
        attempts = attempts.filter(provider_name=provider)

    attempts_list = list(attempts)
    if not attempts_list:
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summary": {"requests": 0},
            "by_task_type": [],
            "by_provider": [],
        }

    p_tok = sum((a["usage_json"] or {}).get("prompt_tokens", 0) or 0 for a in attempts_list)
    c_tok = sum((a["usage_json"] or {}).get("completion_tokens", 0) or 0 for a in attempts_list)
    success_count = sum(1 for a in attempts_list if a["success"])
    total_lat = sum(a.get("latency_ms") or 0 for a in attempts_list)
    total = len(attempts_list)

    total_cost = 0.0
    for a in attempts_list:
        usage = a["usage_json"] or {}
        total_cost += _estimate_cost(
            a["model_name"],
            usage.get("prompt_tokens", 0) or 0,
            usage.get("completion_tokens", 0) or 0,
        )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "summary": {
            "requests": total,
            "success_rate_pct": round(success_count / max(total, 1) * 100, 1),
            "total_tokens": p_tok + c_tok,
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "cost_approx": round(total_cost, 4),
            "avg_latency_ms": round(total_lat / max(total, 1)),
        },
        "by_task_type": _build_group_rows(attempts_list, "task_type"),
        "by_provider": _build_group_rows(attempts_list, "provider"),
    }
