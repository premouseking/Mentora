"""
题目 payload 规范化与结构校验。

约定：
- Agent 工具与 fast path 共用同一套校验逻辑
- 仅做本地结构校验，LLM 质量门禁在 batch_validation 模块

@module mentora/assessment/services/quiz_item_normalization
"""

from __future__ import annotations

import json
from typing import Any

_OPTION_LABELS = ("A", "B", "C", "D")


def coerce_item_data(raw_item: Any) -> dict | None:
    """LLM 偶发把题目序列化为 JSON 字符串，需先反序列化。"""
    if isinstance(raw_item, dict):
        return raw_item
    if isinstance(raw_item, str):
        text = raw_item.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def normalize_options(raw_options: list) -> list[dict]:
    options: list[dict] = []
    for idx, option in enumerate(raw_options[:4]):
        if isinstance(option, str):
            options.append({"label": _OPTION_LABELS[idx], "text": option.strip()})
            continue
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or _OPTION_LABELS[idx]).strip().upper()[:1]
        if label not in _OPTION_LABELS:
            label = _OPTION_LABELS[idx]
        text = str(option.get("text") or "").strip()
        options.append({"label": label, "text": text})
    while len(options) < 4:
        label = _OPTION_LABELS[len(options)]
        options.append({"label": label, "text": "以上说法不正确"})
    return options


def normalize_correct_answer(raw: Any) -> str | None:
    text = str(raw or "").strip().upper()
    if text[:1] in _OPTION_LABELS:
        return text[:1]
    for label in _OPTION_LABELS:
        if label in text.split():
            return label
    return None


def validate_item_payload(
    item_data: dict,
    *,
    allowed_evidence_ids: set[str],
    fallback_evidence_ids: list[str],
) -> tuple[dict | None, str | None]:
    question_text = str(item_data.get("question_text") or "").strip()
    if not question_text:
        return None, "题干不能为空"

    raw_options = item_data.get("options_json") or item_data.get("options") or []
    if not isinstance(raw_options, list) or len(raw_options) < 4:
        return None, "单选题必须包含 4 个选项"

    options = normalize_options(raw_options)
    correct_answer = normalize_correct_answer(item_data.get("correct_answer"))
    if correct_answer is None:
        return None, "正确答案必须是 A/B/C/D 之一"

    evidence_ids = [
        str(eid).strip()
        for eid in item_data.get("source_evidence_ids", [])
        if str(eid).strip()
    ]
    if allowed_evidence_ids:
        evidence_ids = [eid for eid in evidence_ids if eid in allowed_evidence_ids]
    if not evidence_ids:
        evidence_ids = (
            [eid for eid in fallback_evidence_ids if eid in allowed_evidence_ids]
            if allowed_evidence_ids
            else fallback_evidence_ids
        )

    return {
        "question_type": item_data.get("question_type", "single_choice"),
        "question_text": question_text,
        "correct_answer": correct_answer,
        "difficulty": int(item_data.get("difficulty") or 3),
        "options_json": options,
        "explanation": str(item_data.get("explanation") or "").strip(),
        "source_evidence_ids": evidence_ids,
        "topic_id": str(item_data.get("topic_id") or ""),
    }, None


def normalize_raw_items(
    raw_items: list[Any],
    *,
    allowed_evidence_ids: set[str],
    fallback_evidence_ids: list[str],
) -> tuple[list[dict], list[dict]]:
    """批量规范化题目，返回 (accepted, skipped)。"""
    accepted: list[dict] = []
    skipped: list[dict] = []
    for raw_item in raw_items:
        item_data = coerce_item_data(raw_item)
        if item_data is None:
            skipped.append({"error": "题目格式无效"})
            continue
        normalized, error = validate_item_payload(
            item_data,
            allowed_evidence_ids=allowed_evidence_ids,
            fallback_evidence_ids=fallback_evidence_ids,
        )
        if normalized is None:
            skipped.append({"error": error or "题目格式无效"})
            continue
        accepted.append(normalized)
    return accepted, skipped
