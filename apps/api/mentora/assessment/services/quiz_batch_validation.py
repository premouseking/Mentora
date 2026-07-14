"""
批量题目质量门禁——一次 LLM 调用审核整套题。

@module mentora/assessment/services/quiz_batch_validation
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from mentora.model_gateway.exceptions import StructuredOutputError

logger = logging.getLogger(__name__)


class BatchItemValidation(BaseModel):
    index: int = Field(description="题目序号，从 0 开始")
    valid: bool = Field(description="是否通过")
    issues: list[str] = Field(default_factory=list)


class BatchQuizValidationResult(BaseModel):
    items: list[BatchItemValidation] = Field(default_factory=list)


async def validate_quiz_batch_async(
    normalized_items: list[dict],
    *,
    evidence_context: str,
) -> dict[int, list[str]]:
    """一次 LLM 审核多道题，返回 {index: issues[]}；通过则 issues 为空。"""
    if not normalized_items:
        return {}

    from mentora.agent_runtime.views import get_gateway
    from mentora.model_gateway.schemas import Message

    lines: list[str] = []
    for idx, item in enumerate(normalized_items):
        options = "\n".join(
            f"{o['label']}: {o['text']}" for o in item.get("options_json") or []
        )
        lines.append(
            f"[{idx}] 题干：{item['question_text']}\n选项：\n{options}\n"
            f"答案：{item['correct_answer']}\n证据：{', '.join(item.get('source_evidence_ids') or [])}"
        )

    check_rules = (
        "你是题目质量审核员。请逐题检查：\n"
        "1. 选项互斥\n2. 单选题答案唯一\n3. 答案能从资料中找到依据\n"
        "返回 JSON：items 数组，每项含 index/valid/issues。"
    )
    user_content = (
        f"资料原文摘要：\n{evidence_context[:4000]}\n\n"
        f"待审核题目：\n" + "\n\n".join(lines)
    )
    messages = [
        Message(role="system", content=check_rules),
        Message(role="user", content=user_content),
    ]

    gateway = get_gateway()
    issues_by_index: dict[int, list[str]] = {}

    try:
        resp = await gateway.chat(
            task_type="assessor",
            messages=messages,
            structured_output_schema=BatchQuizValidationResult,
        )
        if resp.parsed_output is not None:
            parsed = BatchQuizValidationResult.model_validate(resp.parsed_output)
            for entry in parsed.items:
                if not entry.valid:
                    issues_by_index[entry.index] = list(entry.issues)
            return issues_by_index
    except StructuredOutputError:
        logger.warning("批量质检结构化输出失败，降级为非结构化解析")

    try:
        resp = await gateway.chat(task_type="assessor", messages=messages)
        content = (resp.content or "").strip()
        if content:
            data = json.loads(content)
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                for entry in data["items"]:
                    if not entry.get("valid", True):
                        issues_by_index[int(entry.get("index", 0))] = [
                            str(i) for i in (entry.get("issues") or [])
                        ]
    except Exception:
        logger.exception("批量质检降级解析失败")

    return issues_by_index
