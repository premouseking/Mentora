"""
测验生成编排：fast path、缓存键、落库组卷。

@module mentora/assessment/services/quiz_generation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async

from mentora.assessment.services.quiz_paper_parser import parse_quiz_items_from_content
from mentora.assessment.services.quiz_batch_validation import validate_quiz_batch_async
from mentora.assessment.services.quiz_item_normalization import normalize_raw_items
from mentora.model_gateway.schemas import Message

logger = logging.getLogger(__name__)

ASYNC_GENERATION_MIN_COUNT = 10


class QuizGenerationError(RuntimeError):
    """出题失败，携带可展示错误码。"""

    def __init__(self, message: str, *, code: str = "generation_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class QuizGenerationRequest:
    course_session_id: str
    count: int
    difficulty: str
    source_version_ids: list[str]
    source_evidence_ids: list[str]
    evidence_units: list[Any]
    source_titles: dict[str, str]
    unit_id: str = ""
    unit_title: str = ""
    task_id: str = ""
    mode: str = "fast"
    force_regenerate: bool = False


@dataclass
class QuizGenerationMetrics:
    evidence_ms: float = 0.0
    llm_ms: float = 0.0
    persist_ms: float = 0.0
    validation_ms: float = 0.0
    total_ms: float = 0.0
    path: str = "fast"
    item_count: int = 0
    skipped_count: int = 0
    tool_rounds: int = 0


def build_generation_cache_key(req: QuizGenerationRequest) -> str:
    payload = {
        "course_session_id": req.course_session_id,
        "task_id": req.task_id,
        "source_evidence_ids": sorted(req.source_evidence_ids),
        "source_version_ids": sorted(req.source_version_ids),
        "count": req.count,
        "difficulty": req.difficulty,
        "unit_id": req.unit_id,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return digest[:64]


def find_reusable_session_id(cache_key: str) -> str | None:
    from mentora.assessment.models import AssessmentSession, QuizGenerationJob

    job = (
        QuizGenerationJob.objects.filter(
            generation_cache_key=cache_key,
            status=QuizGenerationJob.Status.SUCCEEDED,
            result_session_id__isnull=False,
        )
        .order_by("-updated_at")
        .first()
    )
    if job is None:
        return None
    session = AssessmentSession.objects.filter(id=job.result_session_id).first()
    if session is None:
        return None
    if session.status == AssessmentSession.Status.COMPLETED:
        return str(session.id)
    return str(session.id)


def build_fast_generation_messages(req: QuizGenerationRequest) -> list[Message]:
    evidence_lines = []
    for idx, unit in enumerate(req.evidence_units, 1):
        title = req.source_titles.get(unit.source_version_id, unit.source_version_id)
        content = unit.content.strip().replace("\n", " ")
        evidence_lines.append(
            f"{idx}. evidence_id={unit.id} source={title} page={unit.page_number}\n{content}"
        )
    allowed_ids = [str(unit.id) for unit in req.evidence_units]
    user_text = (
        f"请生成 {req.count} 道单选题，难度：{req.difficulty}。\n"
        f"学习单元：{req.unit_title or '综合练习'}\n"
        "要求：\n"
        "1. 只基于下方证据出题\n"
        "2. 每题 4 个选项，正确答案只能是 A/B/C/D\n"
        "3. 每题必须填写 source_evidence_ids\n"
        f"允许的 evidence_id：{', '.join(allowed_ids) or '无'}\n\n"
        "课程资料证据：\n" + "\n\n".join(evidence_lines)
    )
    return [
        Message(
            role="system",
            content=(
                "你是 Mentora 评估专家。只输出 JSON，不要 Markdown 代码块。"
                "格式示例："
                '{"items":[{"question_text":"题干","correct_answer":"A",'
                '"difficulty":3,'
                '"options":[{"label":"A","text":"选项A"},{"label":"B","text":"选项B"},'
                '{"label":"C","text":"选项C"},{"label":"D","text":"选项D"}],'
                '"explanation":"解析","source_evidence_ids":["证据UUID"]}]}'
            ),
        ),
        Message(role="user", content=user_text),
    ]


async def _fetch_quiz_items_from_llm(req: QuizGenerationRequest) -> list[dict]:
    """一次 LLM 调用 + 宽松 JSON 解析；避免 strict schema 导致整批失败。"""
    from mentora.agent_runtime.views import get_gateway
    from mentora.model_gateway.exceptions import ProviderError

    gateway = get_gateway()
    messages = build_fast_generation_messages(req)

    for attempt in range(2):
        try:
            resp = await gateway.chat(task_type="assessor", messages=messages)
        except ProviderError as exc:
            raise QuizGenerationError(f"模型生成题目失败: {exc}", code="model_timeout") from exc

        items = parse_quiz_items_from_content(resp.content or "")
        if items:
            logger.info(
                "quiz fast path parsed items count=%s attempt=%s",
                len(items),
                attempt + 1,
            )
            return items

        if attempt == 0:
            logger.warning("quiz paper parse failed, retrying LLM once")
            messages = [
                *messages,
                Message(
                    role="user",
                    content=(
                        "上次输出无法解析。请只返回 JSON，根对象含 items 数组；"
                        "每题含 question_text、correct_answer、options、source_evidence_ids。"
                    ),
                ),
            ]

    raise QuizGenerationError(
        "模型返回格式无法解析为题目列表，请重试",
        code="invalid_format",
    )


def _build_evidence_context(req: QuizGenerationRequest) -> str:
    parts: list[str] = []
    for unit in req.evidence_units:
        title = req.source_titles.get(unit.source_version_id, unit.source_version_id)
        parts.append(f"[{unit.id}] {title} p{unit.page_number}: {unit.content[:500]}")
    return "\n".join(parts)


async def persist_normalized_items(
    *,
    course_session_id: str,
    normalized_items: list[dict],
    unit_id: str,
    run_batch_validation: bool = True,
    evidence_context: str = "",
) -> tuple[list[str], list[dict]]:
    from mentora.assessment.services import create_item, create_session, publish_item

    validation_issues: dict[int, list[str]] = {}
    if run_batch_validation and normalized_items and evidence_context:
        t0 = time.perf_counter()
        validation_issues = await validate_quiz_batch_async(
            normalized_items,
            evidence_context=evidence_context,
        )
        logger.info(
            "quiz batch validation done items=%s flagged=%s ms=%.0f",
            len(normalized_items),
            len(validation_issues),
            (time.perf_counter() - t0) * 1000,
        )

    created_ids: list[str] = []
    skipped: list[dict] = []
    for idx, normalized in enumerate(normalized_items):
        ai_issues = validation_issues.get(idx)
        result = await sync_to_async(create_item)(
            course_session_id=course_session_id,
            question_type=normalized["question_type"],
            question_text=normalized["question_text"],
            correct_answer=normalized["correct_answer"],
            topic_id=normalized["topic_id"],
            difficulty=normalized["difficulty"],
            options_json=normalized["options_json"],
            explanation=normalized["explanation"],
            source_evidence_ids=normalized["source_evidence_ids"],
            status="draft",
            source_type="ai",
        )
        if ai_issues:
            from mentora.assessment.models import AssessmentItemRevision

            revision = await sync_to_async(
                AssessmentItemRevision.objects.get
            )(id=result["revision_id"])
            revision.validation_issues = ai_issues
            await sync_to_async(revision.save)(update_fields=["validation_issues"])
        await sync_to_async(publish_item)(result["item_id"])
        created_ids.append(result["item_id"])

    if not created_ids:
        return [], skipped

    session_result = await sync_to_async(create_session)(
        course_session_id=course_session_id,
        item_ids=created_ids,
        unit_id=unit_id,
    )
    return session_result["session_id"], skipped


async def run_quiz_generation_fast(req: QuizGenerationRequest) -> tuple[str, QuizGenerationMetrics]:
    metrics = QuizGenerationMetrics(path="fast")
    started = time.perf_counter()
    allowed = {str(unit.id) for unit in req.evidence_units}
    fallback = [str(unit.id) for unit in req.evidence_units[:3]]

    llm_started = time.perf_counter()
    raw_items = await _fetch_quiz_items_from_llm(req)
    metrics.llm_ms = (time.perf_counter() - llm_started) * 1000

    normalized, skipped = normalize_raw_items(
        raw_items,
        allowed_evidence_ids=allowed,
        fallback_evidence_ids=fallback,
    )
    if not normalized:
        raise QuizGenerationError(
            "题目格式无效，无法创建测验",
            code="invalid_format",
        )

    persist_started = time.perf_counter()
    session_ids, persist_skipped = await persist_normalized_items(
        course_session_id=req.course_session_id,
        normalized_items=normalized[: req.count],
        unit_id=req.unit_id,
        run_batch_validation=True,
        evidence_context=_build_evidence_context(req),
    )
    metrics.persist_ms = (time.perf_counter() - persist_started) * 1000
    metrics.skipped_count = len(skipped) + len(persist_skipped)
    metrics.item_count = len(normalized[: req.count])
    metrics.total_ms = (time.perf_counter() - started) * 1000

    if not session_ids:
        raise QuizGenerationError("没有可用的题目创建测验", code="validation_rejected")

    logger.info(
        "quiz fast generation ok session=%s items=%s skipped=%s total_ms=%.0f",
        session_ids,
        metrics.item_count,
        metrics.skipped_count,
        metrics.total_ms,
    )
    return session_ids, metrics


def run_quiz_generation_fast_sync(req: QuizGenerationRequest) -> tuple[str, QuizGenerationMetrics]:
    return asyncio.run(run_quiz_generation_fast(req))


def should_use_async_generation(req: QuizGenerationRequest, *, async_flag: bool) -> bool:
    if async_flag:
        return True
    if req.mode == "agent":
        return req.count >= ASYNC_GENERATION_MIN_COUNT
    return req.count >= ASYNC_GENERATION_MIN_COUNT
