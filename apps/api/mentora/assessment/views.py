"""刷题模式 HTTP 接口。"""

from __future__ import annotations

import json
import logging
import time

from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.assessment.models import AssessmentSession
from mentora.assessment.services import complete_session, submit_attempt
from mentora.assessment.services.quiz_evidence import get_scoped_evidence, get_source_titles
from mentora.assessment.services.quiz_generation import (
    QuizGenerationError,
    QuizGenerationRequest,
    build_generation_cache_key,
    find_reusable_session_id,
    run_quiz_generation_fast_sync,
    should_use_async_generation,
)
from mentora.assessment.services.quiz_generation_jobs import (
    create_generation_job,
    enqueue_generation_job,
    get_generation_job,
)

logger = logging.getLogger(__name__)

DEFAULT_TASK_QUIZ_COUNT = 5
DEFAULT_QUIZ_COUNT = 5


def _parse_json(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("无效 JSON")


def _json_error(message: str, status: int = 400, *, code: str | None = None) -> Response:
    payload: dict = {"error": message}
    if code:
        payload["code"] = code
    return Response(payload, status=status)


def _resolve_task_unit_id(task_id: str, course_session_id: str, *, owner=None) -> tuple[str, Response | None]:
    if not task_id:
        return "", None

    from mentora.learning.services.task_sources import resolve_learning_task

    task = resolve_learning_task(task_id, owner=owner)
    if task is None:
        return "", _json_error("任务不存在", 400)

    plan = getattr(task.revision, "learning_plan", None)
    if plan is None or str(plan.course_session_id) != str(course_session_id):
        return "", _json_error("任务不属于当前课程会话", 400)

    return str(task.unit_id), None


def _resolve_course_session_id(body: dict) -> tuple[str | None, Response | None]:
    course_session_id = str(body.get("course_session_id") or "").strip()
    if course_session_id:
        return course_session_id, None
    if settings.DEBUG and settings.DEV_COURSE_SESSION_ID:
        return settings.DEV_COURSE_SESSION_ID, None
    return None, _json_error("缺少 course_session_id", 400)


def _serialize_session(session_id: str, *, owner=None) -> dict | None:
    try:
        session = AssessmentSession.objects.get(
            id=session_id, **({"owner": owner} if owner is not None else {}),
        )
    except AssessmentSession.DoesNotExist:
        return None

    from mentora.retrieval.models import EvidenceUnit
    from mentora.assessment.models import AssessmentItemRevision

    attempts = session.attempts.select_related("item").order_by("position")
    attempts = list(attempts)
    revision_ids = [
        attempt.item.current_revision_id
        for attempt in attempts
        if attempt.item.current_revision_id
    ]
    revision_map = {
        revision.id: revision
        for revision in AssessmentItemRevision.objects.filter(id__in=revision_ids)
    }
    evidence_ids = []
    for attempt in attempts:
        revision = revision_map.get(attempt.item.current_revision_id)
        if revision:
            evidence_ids.extend(revision.source_evidence_ids or [])
    evidence_map = {
        str(unit.id): unit
        for unit in EvidenceUnit.objects.filter(id__in=evidence_ids)
    }
    source_titles_by_version = get_source_titles(
        list({unit.source_version_id for unit in evidence_map.values()})
    )

    items = []
    for attempt in attempts:
        item = attempt.item
        revision = revision_map.get(item.current_revision_id)
        source_links = []
        source_evidence_ids = revision.source_evidence_ids if revision else []
        for evidence_id in source_evidence_ids or []:
            unit = evidence_map.get(str(evidence_id))
            if not unit:
                continue
            source_links.append({
                "evidence_id": str(unit.id),
                "source_version_id": unit.source_version_id,
                "title": source_titles_by_version.get(unit.source_version_id, unit.source_version_id),
                "page_number": unit.page_number,
                "snippet": unit.content[:120],
            })

        items.append({
            "attempt_id": str(attempt.id),
            "item_id": str(item.id),
            "position": attempt.position,
            "question_type": item.question_type,
            "question_text": revision.question_text if revision else "",
            "options": revision.options_json if revision and revision.options_json else [],
            "correct_answer": revision.correct_answer if revision else "",
            "explanation": revision.explanation if revision else "",
            "difficulty": item.difficulty,
            "source_links": source_links,
            "user_answer": attempt.user_answer,
            "is_correct": attempt.is_correct,
        })

    return {
        "session_id": str(session.id),
        "course_session_id": str(session.course_session_id),
        "status": session.status,
        "total_items": session.total_items,
        "correct_count": session.correct_count,
        "score_pct": session.score_pct,
        "items": items,
    }


def _parse_reuse_query_params(request) -> tuple[QuizGenerationRequest | None, Response | None]:
    """与 generate 共用 cache key 构造，复用查找须解析 task 对应 unit_id。"""
    course_session_id = str(request.GET.get("course_session_id") or "").strip()
    if not course_session_id:
        return None, _json_error("缺少 course_session_id", 400)

    task_id = str(request.GET.get("task_id") or "").strip()
    unit_id = str(request.GET.get("unit_id") or "").strip()
    if task_id and not unit_id:
        unit_id, task_error = _resolve_task_unit_id(task_id, course_session_id)
        if task_error is not None:
            return None, task_error

    req = QuizGenerationRequest(
        course_session_id=course_session_id,
        count=int(request.GET.get("count") or DEFAULT_TASK_QUIZ_COUNT),
        difficulty=str(request.GET.get("difficulty") or "综合"),
        source_version_ids=[
            str(v).strip()
            for v in (request.GET.get("source_version_ids") or "").split(",")
            if str(v).strip()
        ],
        source_evidence_ids=[
            str(v).strip()
            for v in (request.GET.get("source_evidence_ids") or "").split(",")
            if str(v).strip()
        ],
        evidence_units=[],
        source_titles={},
        task_id=task_id,
        unit_id=unit_id,
    )
    return req, None


def _build_generation_request(
    body: dict,
    *,
    course_session_id: str,
    source_version_ids: list[str],
    source_evidence_ids: list[str],
    count: int,
    difficulty: str,
    task_id: str,
    unit_id: str,
    unit_title: str,
    evidence_units,
    source_titles: dict[str, str],
) -> QuizGenerationRequest:
    mode = str(body.get("mode") or "fast").strip().lower()
    if mode not in {"fast", "agent"}:
        mode = "fast"
    return QuizGenerationRequest(
        course_session_id=course_session_id,
        count=count,
        difficulty=difficulty,
        source_version_ids=source_version_ids,
        source_evidence_ids=source_evidence_ids,
        evidence_units=evidence_units,
        source_titles=source_titles,
        unit_id=unit_id,
        unit_title=unit_title,
        task_id=task_id,
        mode=mode,
        force_regenerate=bool(body.get("force_regenerate")),
    )


@extend_schema(
    summary="生成测验试卷",
    description="LLM 根据课程资料自动生成题目并创建测验会话",
)
@api_view(["POST"])
def generate_quiz_session(request):
    if not settings.LLM_API_KEY:
        return _json_error("LLM_API_KEY 未配置，无法生成题目", 503)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    source_version_ids = [str(s).strip() for s in body.get("source_version_ids", []) if str(s).strip()]
    source_evidence_ids = [
        str(eid).strip() for eid in body.get("source_evidence_ids", []) if str(eid).strip()
    ]
    task_id = str(body.get("task_id") or "").strip()

    if not source_version_ids and not source_evidence_ids:
        return _json_error("请至少选择一个课程文件或指定任务证据", 400)

    default_count = DEFAULT_TASK_QUIZ_COUNT if task_id else DEFAULT_QUIZ_COUNT
    count = body.get("count", default_count)
    try:
        count = max(1, min(int(count), 20))
    except (TypeError, ValueError):
        count = default_count
    difficulty = str(body.get("difficulty") or "综合").strip()
    course_session_id, error_response = _resolve_course_session_id(body)
    if error_response is not None:
        return error_response
    from mentora.courses.models import CourseCreationSession
    if not CourseCreationSession.objects.filter(
        id=course_session_id, owner=request.user,
    ).exists():
        return _json_error("课程会话不存在", 404)
    from mentora.knowledge.models import SourceVersion
    if SourceVersion.objects.filter(
        id__in=source_version_ids, source__owner=request.user,
    ).count() != len(set(source_version_ids)):
        return _json_error("课程资料不存在或无权访问", 404)

    evidence_started = time.perf_counter()
    evidence_units = get_scoped_evidence(
        source_version_ids,
        evidence_ids=source_evidence_ids or None,
    )
    evidence_ms = (time.perf_counter() - evidence_started) * 1000

    if source_evidence_ids:
        found_ids = {str(unit.id) for unit in evidence_units}
        missing = [eid for eid in source_evidence_ids if eid not in found_ids]
        if missing:
            return _json_error("部分任务证据不存在或不在所选资料范围内", 400)
        if not source_version_ids:
            source_version_ids = sorted({str(unit.source_version_id) for unit in evidence_units})
    if not evidence_units:
        return _json_error("所选资料还没有可用于出题的解析证据，请先完成文件解析", 400)

    source_titles = get_source_titles(source_version_ids)
    unit_id, task_error = _resolve_task_unit_id(
        task_id, course_session_id, owner=request.user,
    )
    if task_error is not None:
        return task_error

    unit_title = ""
    if unit_id:
        from mentora.learning.models import LearningPlanUnit

        unit = LearningPlanUnit.objects.filter(id=unit_id).first()
        if unit:
            unit_title = unit.title or ""

    req = _build_generation_request(
        body,
        course_session_id=course_session_id,
        source_version_ids=source_version_ids,
        source_evidence_ids=source_evidence_ids,
        count=count,
        difficulty=difficulty,
        task_id=task_id,
        unit_id=unit_id,
        unit_title=unit_title,
        evidence_units=evidence_units,
        source_titles=source_titles,
    )
    cache_key = build_generation_cache_key(req)

    if not req.force_regenerate:
        reused_session_id = find_reusable_session_id(cache_key)
        if reused_session_id:
            data = _serialize_session(reused_session_id, owner=request.user)
            if data is not None:
                data["reused"] = True
                logger.info(
                    "quiz generation reused session=%s cache_key=%s evidence_ms=%.0f",
                    reused_session_id,
                    cache_key[:12],
                    evidence_ms,
                )
                return Response(data, status=201)

    async_requested = should_use_async_generation(
        req,
        async_flag=bool(body.get("async")),
    )

    if async_requested:
        job = create_generation_job(req, owner=request.user)
        enqueue_generation_job(str(job.id), req)
        return Response(
            {
                "job_id": str(job.id),
                "status": job.status,
                "progress": job.progress,
                "progress_pct": job.progress_pct,
            },
            status=202,
        )

    started = time.perf_counter()
    try:
        if req.mode == "agent":
            from mentora.assessment.services.agent_generation import run_assessor_quiz_generation_sync

            session_id = run_assessor_quiz_generation_sync(
                course_session_id=req.course_session_id,
                count=req.count,
                difficulty=req.difficulty,
                source_version_ids=req.source_version_ids,
                source_evidence_ids=req.source_evidence_ids,
                evidence_units=req.evidence_units,
                source_titles=req.source_titles,
                unit_id=req.unit_id,
                unit_title=req.unit_title,
            )
        else:
            session_id, metrics = run_quiz_generation_fast_sync(req)
            logger.info(
                "quiz generation fast path session=%s evidence_ms=%.0f llm_ms=%.0f total_ms=%.0f",
                session_id,
                evidence_ms,
                metrics.llm_ms,
                metrics.total_ms,
            )
    except QuizGenerationError as exc:
        logger.warning("quiz generation failed code=%s msg=%s", exc.code, exc)
        return _json_error(str(exc), 502, code=exc.code)
    except Exception as exc:
        logger.exception("quiz generation unexpected failure")
        return _json_error(f"出题失败: {str(exc)}", 502, code="generation_failed")

    total_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "quiz generation done session=%s mode=%s count=%s total_ms=%.0f",
        session_id,
        req.mode,
        req.count,
        total_ms,
    )

    from mentora.assessment.models import QuizGenerationJob

    QuizGenerationJob.objects.create(
        owner=request.user,
        status=QuizGenerationJob.Status.SUCCEEDED,
        progress="生成完成",
        progress_pct=100,
        generation_cache_key=cache_key,
        request_payload={
            "course_session_id": req.course_session_id,
            "count": req.count,
            "task_id": req.task_id,
            "mode": req.mode,
        },
        result_session_id=session_id,
    )

    data = _serialize_session(session_id, owner=request.user)
    if data is None:
        return _json_error("生成测验成功但无法读取会话", 500)
    data["reused"] = False
    return Response(data, status=201)


@api_view(["GET"])
@extend_schema(summary="Quiz Generation Job Detail")
def quiz_generation_job_detail(request, job_id):
    data = get_generation_job(str(job_id), owner=request.user)
    if data is None:
        return _json_error("出题任务不存在", 404)
    if data.get("session_id"):
        session = _serialize_session(data["session_id"], owner=request.user)
        if session:
            data["session"] = session
    return Response(data)


@api_view(["GET"])
@extend_schema(summary="Quiz Session Detail")
def quiz_session_detail(request, session_id):
    data = _serialize_session(str(session_id), owner=request.user)
    if data is None:
        return _json_error("测验不存在", 404)
    return Response(data)


@api_view(["GET"])
@extend_schema(summary="Find Reusable Quiz Session")
def find_quiz_session(request):
    """按 cache key 参数查找可复用测验（任务练习预加载）。"""
    req, error_response = _parse_reuse_query_params(request)
    if error_response is not None:
        return error_response

    cache_key = build_generation_cache_key(req)
    session_id = find_reusable_session_id(cache_key)
    if not session_id:
        return Response({"session": None})
    session = _serialize_session(session_id, owner=request.user)
    return Response({"session": session, "reused": True})


@api_view(["POST"])
@extend_schema(summary="Submit Quiz Attempt")
def submit_quiz_attempt(request, session_id):
    if not AssessmentSession.objects.filter(id=session_id, owner=request.user).exists():
        return _json_error("测验不存在", 404)
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    item_id = str(body.get("item_id") or "").strip()
    user_answer = str(body.get("user_answer") or "").strip()
    if not item_id or not user_answer:
        return _json_error("item_id 和 user_answer 不能为空", 400)

    try:
        result = submit_attempt(
            session_id=str(session_id),
            item_id=item_id,
            user_answer=user_answer,
            duration_seconds=body.get("duration_seconds"),
        )
    except Exception as exc:
        return _json_error(f"提交答案失败: {str(exc)}", 400)

    return Response(result)


@api_view(["POST"])
@extend_schema(summary="Complete Quiz Session")
def complete_quiz_session(request, session_id):
    if not AssessmentSession.objects.filter(id=session_id, owner=request.user).exists():
        return _json_error("测验不存在", 404)
    try:
        result = complete_session(str(session_id))
    except Exception as exc:
        return _json_error(f"完成测验失败: {str(exc)}", 400)
    data = _serialize_session(result["session_id"], owner=request.user)
    return Response(data or result)
