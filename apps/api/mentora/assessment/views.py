"""刷题模式 HTTP 接口。"""

from __future__ import annotations

import asyncio
import json

from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from mentora.assessment.models import AssessmentItem, AssessmentSession
from mentora.assessment.schemas import GeneratedQuizPaper
from mentora.assessment.services import (
    complete_session,
    create_item,
    create_session,
    submit_attempt,
)
from mentora.model_gateway.schemas import Message

MAX_CONTEXT_EVIDENCE = 18


def _parse_json(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("无效 JSON")


def _json_error(message: str, status: int = 400) -> Response:
    return Response({"error": message}, status=status)


def _resolve_course_session_id(body: dict) -> tuple[str | None, Response | None]:
    course_session_id = str(body.get("course_session_id") or "").strip()
    if course_session_id:
        return course_session_id, None
    if settings.DEBUG and settings.DEV_COURSE_SESSION_ID:
        return settings.DEV_COURSE_SESSION_ID, None
    return None, _json_error("缺少 course_session_id", 400)


def _get_source_titles(source_version_ids: list[str]) -> dict[str, str]:
    from mentora.knowledge.models import SourceVersion

    versions = SourceVersion.objects.select_related("source").filter(id__in=source_version_ids)
    titles: dict[str, str] = {}
    for version in versions:
        titles[str(version.id)] = (
            version.source.display_title
            or version.original_filename
            or f"资料 {str(version.id)[:8]}"
        )
    return titles


def _get_scoped_evidence(source_version_ids: list[str]):
    from mentora.retrieval.models import EvidenceUnit

    return list(
        EvidenceUnit.objects.filter(source_version_id__in=source_version_ids)
        .order_by("source_version_id", "page_number", "created_at")[:MAX_CONTEXT_EVIDENCE]
    )


def _build_generation_prompt(
    *,
    evidence_units,
    source_titles: dict[str, str],
    count: int,
    difficulty: str,
) -> list[Message]:
    evidence_lines = []
    for idx, unit in enumerate(evidence_units, 1):
        title = source_titles.get(unit.source_version_id, unit.source_version_id)
        content = unit.content.strip().replace("\n", " ")
        evidence_lines.append(
            f"{idx}. evidence_id={unit.id} source={title} page={unit.page_number}\n{content}"
        )

    system = (
        "你是 Mentora 的课程刷题出题助手。请只基于用户提供的课程资料证据生成单选题，"
        "不得编造资料外知识。每题必须有 4 个选项，正确答案只能是 A/B/C/D，"
        "解析要说明依据，并尽量引用 evidence_id。"
    )
    user = (
        f"请生成 {count} 道单选题，难度要求：{difficulty or '综合'}。\n"
        "返回结构必须符合 schema；source_evidence_ids 只允许使用下面列出的 evidence_id。\n\n"
        "课程资料证据：\n" + "\n\n".join(evidence_lines)
    )
    return [Message(role="system", content=system), Message(role="user", content=user)]


def _normalize_options(raw_options: list[dict]) -> list[dict]:
    labels = ["A", "B", "C", "D"]
    options: list[dict] = []
    for idx, option in enumerate(raw_options[:4]):
        label = str(option.get("label") or labels[idx]).strip().upper()[:1]
        if label not in labels:
            label = labels[idx]
        text = str(option.get("text") or "").strip()
        options.append({"label": label, "text": text})
    while len(options) < 4:
        label = labels[len(options)]
        options.append({"label": label, "text": "以上说法不正确"})
    return options


def _serialize_session(session_id: str) -> dict | None:
    try:
        session = AssessmentSession.objects.get(id=session_id)
    except AssessmentSession.DoesNotExist:
        return None

    from mentora.retrieval.models import EvidenceUnit

    attempts = session.attempts.select_related("item").order_by("position")
    evidence_ids = []
    for attempt in attempts:
        evidence_ids.extend(attempt.item.source_evidence_ids or [])
    evidence_map = {
        str(unit.id): unit
        for unit in EvidenceUnit.objects.filter(id__in=evidence_ids)
    }
    source_titles_by_version = _get_source_titles(
        list({unit.source_version_id for unit in evidence_map.values()})
    )

    items = []
    for attempt in attempts:
        item = attempt.item
        source_links = []
        for evidence_id in item.source_evidence_ids or []:
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
            "question_text": item.question_text,
            "options": item.options_json or [],
            "correct_answer": item.correct_answer,
            "explanation": item.explanation,
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


@extend_schema(
    summary="生成测验试卷",
    description="LLM 根据课程资料自动生成题目并创建测验会话",
    request={"application/json": {"type": "object", "properties": {
        "course_session_id": {"type": "string"},
        "source_version_ids": {"type": "array", "items": {"type": "string"}},
        "count": {"type": "integer", "default": 5},
        "difficulty": {"type": "string", "default": "综合"},
    }}},
    responses={201: OpenApiParameter("session_id", str)},
)
@api_view(["POST"])
@extend_schema(summary="Generate Quiz Session")
def generate_quiz_session(request):
    if not settings.LLM_API_KEY:
        return _json_error("LLM_API_KEY 未配置，无法生成题目", 503)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    source_version_ids = [str(s).strip() for s in body.get("source_version_ids", []) if str(s).strip()]
    if not source_version_ids:
        return _json_error("请至少选择一个课程文件", 400)

    count = body.get("count", 10)
    try:
        count = max(1, min(int(count), 20))
    except (TypeError, ValueError):
        count = 10
    difficulty = str(body.get("difficulty") or "综合").strip()
    course_session_id, error_response = _resolve_course_session_id(body)
    if error_response is not None:
        return error_response

    evidence_units = _get_scoped_evidence(source_version_ids)
    if not evidence_units:
        return _json_error("所选资料还没有可用于出题的解析证据，请先完成文件解析", 400)

    source_titles = _get_source_titles(source_version_ids)
    messages = _build_generation_prompt(
        evidence_units=evidence_units,
        source_titles=source_titles,
        count=count,
        difficulty=difficulty,
    )

    try:
        from mentora.agent_runtime.views import get_gateway

        resp = asyncio.run(
            get_gateway().chat(
                task_type="assessment_generate",
                messages=messages,
                structured_output_schema=GeneratedQuizPaper,
            )
        )
    except Exception as exc:
        return _json_error(f"LLM 出题失败: {str(exc)}", 502)

    if resp.parsed_output is None:
        return _json_error("LLM 返回格式异常，请重试", 502)

    allowed_evidence_ids = {str(unit.id) for unit in evidence_units}
    fallback_evidence_ids = [str(unit.id) for unit in evidence_units[:3]]
    item_ids: list[str] = []

    try:
        for raw_item in resp.parsed_output.get("items", [])[:count]:
            options = _normalize_options(raw_item.get("options") or [])
            correct_answer = str(raw_item.get("correct_answer") or "A").strip().upper()[:1]
            if correct_answer not in {"A", "B", "C", "D"}:
                correct_answer = "A"
            evidence_ids = [
                str(eid)
                for eid in raw_item.get("source_evidence_ids", [])
                if str(eid) in allowed_evidence_ids
            ] or fallback_evidence_ids
            created = create_item(
                course_session_id=course_session_id,
                question_type=AssessmentItem.QuestionType.SINGLE_CHOICE,
                question_text=str(raw_item.get("question_text") or "").strip(),
                correct_answer=correct_answer,
                difficulty=int(raw_item.get("difficulty") or 3),
                options_json=options,
                explanation=str(raw_item.get("explanation") or "").strip(),
                source_evidence_ids=evidence_ids,
            )
            item_ids.append(created["item_id"])
        if not item_ids:
            return _json_error("LLM 没有生成有效题目，请重试", 502)
        session = create_session(course_session_id=course_session_id, item_ids=item_ids)
    except Exception as exc:
        return _json_error(f"保存题目失败: {str(exc)}", 500)

    data = _serialize_session(session["session_id"])
    return Response(data or session, status=201)


@api_view(["GET"])
@extend_schema(summary="Quiz Session Detail")
def quiz_session_detail(request, session_id):
    data = _serialize_session(str(session_id))
    if data is None:
        return _json_error("测验不存在", 404)
    return Response(data)


@api_view(["POST"])
@extend_schema(summary="Submit Quiz Attempt")
def submit_quiz_attempt(request, session_id):
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
    try:
        result = complete_session(str(session_id))
    except Exception as exc:
        return _json_error(f"完成测验失败: {str(exc)}", 400)
    data = _serialize_session(result["session_id"])
    return Response(data or result)
