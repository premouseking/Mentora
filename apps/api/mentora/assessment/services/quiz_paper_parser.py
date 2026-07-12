"""
LLM 测验卷响应解析——结构化失败时的降级路径。

@module mentora/assessment/services/quiz_paper_parser
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mentora.assessment.schemas import GeneratedQuizPaper
from mentora.assessment.services.quiz_item_normalization import coerce_item_data
from mentora.model_gateway.structured_output import StructuredOutputValidator

logger = logging.getLogger(__name__)


def _coerce_quiz_item(raw: Any) -> dict | None:
    item_data = coerce_item_data(raw) if not isinstance(raw, dict) else raw
    if not isinstance(item_data, dict):
        return None

    options = (
        item_data.get("options")
        or item_data.get("options_json")
        or item_data.get("choices")
        or []
    )
    if isinstance(options, dict):
        options = [
            {"label": label, "text": text}
            for label, text in options.items()
        ]

    question_text = str(
        item_data.get("question_text")
        or item_data.get("question")
        or item_data.get("stem")
        or "",
    ).strip()
    if not question_text:
        return None

    evidence_ids = (
        item_data.get("source_evidence_ids")
        or item_data.get("evidence_ids")
        or item_data.get("evidence_id")
        or []
    )
    if isinstance(evidence_ids, str):
        evidence_ids = [evidence_ids]

    difficulty_raw = item_data.get("difficulty", 3)
    try:
        difficulty = int(difficulty_raw)
    except (TypeError, ValueError):
        difficulty = 3

    return {
        "question_text": question_text,
        "correct_answer": str(
            item_data.get("correct_answer")
            or item_data.get("answer")
            or "A",
        ),
        "difficulty": difficulty,
        "options": options if isinstance(options, list) else [],
        "explanation": str(item_data.get("explanation") or item_data.get("analysis") or ""),
        "source_evidence_ids": [str(eid) for eid in evidence_ids if str(eid).strip()],
    }


def extract_items_from_payload(payload: Any) -> list[dict]:
    """从多种常见 JSON 形态提取题目列表。"""
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = (
            payload.get("items")
            or payload.get("questions")
            or payload.get("quiz_items")
            or []
        )
        if not candidates and payload.get("question_text"):
            candidates = [payload]
    else:
        return []

    items: list[dict] = []
    for raw in candidates:
        coerced = _coerce_quiz_item(raw)
        if coerced is not None:
            items.append(coerced)
    return items


def parse_quiz_items_from_content(content: str) -> list[dict]:
    """从 LLM 文本响应解析题目，兼容 strict schema 失败的情况。"""
    if not content.strip():
        return []

    validator = StructuredOutputValidator()
    instance, errors = validator.validate(content, GeneratedQuizPaper)
    if instance is not None:
        items = [
            {
                "question_text": item.question_text,
                "correct_answer": item.correct_answer,
                "difficulty": item.difficulty,
                "options": item.options,
                "explanation": item.explanation,
                "source_evidence_ids": item.source_evidence_ids,
            }
            for item in instance.items
            if item.question_text.strip()
        ]
        if items:
            return items

    json_str = validator._extract_json(content)
    if not json_str:
        logger.warning("quiz paper parse: no json extracted errors=%s", errors[:3])
        return []

    try:
        payload = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("quiz paper parse: json decode failed %s", exc)
        return []

    items = extract_items_from_payload(payload)
    if not items:
        logger.warning(
            "quiz paper parse: payload had no usable items errors=%s keys=%s",
            errors[:3],
            list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
        )
    return items
