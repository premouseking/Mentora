"""
课程 Agent 聊天 API：会话列表、历史与 SSE 流式对话。

约定：
- 首条消息无 agent_session_id 时自动创建 CourseAgentSession
- 上下文由 course_context 构建并注入 OrchestratorTask

约束：
- LLM 未配置时返回 503，不创建会话或 assistant 消息

@module mentora/agent_runtime/course_agent_views
"""

from __future__ import annotations

import asyncio
import json
import uuid

from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from mentora.agent_runtime.decorators import rate_limit
from mentora.agent_runtime.models import CourseAgentMessage, CourseAgentSession
from mentora.agent_runtime.services.course_context import (
    build_course_agent_context,
    format_course_context_prompt,
)
from mentora.agent_runtime.services.course_intent import classify_course_chat_intent
from mentora.agent_runtime.services.session_serializers import (
    serialize_course_agent_session_detail,
    serialize_course_agent_session_summary,
)
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.agent_runtime.views import _ensure_runtime, _format_attachment_summary, _parse_history_messages, _resolve_model_id
from mentora.model_gateway.schemas import Message


def _session_title_from_message(message: str) -> str:
    text = message.strip()
    if not text:
        return "新对话"
    return text[:64] + ("…" if len(text) > 64 else "")


def _load_session_history(session: CourseAgentSession) -> list[Message]:
    messages: list[Message] = []
    for item in session.messages.order_by("created_at"):
        if item.role not in {CourseAgentMessage.Role.USER, CourseAgentMessage.Role.ASSISTANT}:
            continue
        content = (item.content or "").strip()
        if not content:
            continue
        messages.append(Message(role=item.role, content=content))
    return messages[-20:]


def _build_course_chat_task(
    *,
    body: dict,
    course_id: str,
    course_context: dict,
    owner_id: str = "",
) -> OrchestratorTask | None:
    user_message = body.get("message", "").strip()
    if not user_message:
        return None

    user_message += _format_attachment_summary(body.get("attachments"))
    user_message = f"{format_course_context_prompt(course_context)}\n\n{user_message}"

    raw_message = body.get("message", "").strip()
    mentions = body.get("mentions") if isinstance(body.get("mentions"), list) else []
    tool_access = classify_course_chat_intent(
        raw_message,
        mentions=mentions,
        current_source_version_id=body.get("current_source_version_id"),
        current_task_id=body.get("current_task_id"),
    )

    course_summary = course_context.get("course_summary") or {}
    return OrchestratorTask(
        id=f"course-chat-{uuid.uuid4().hex[:12]}",
        mode="single",
        agent_role="tutor",
        user_message=user_message,
        context_sources=list(course_context.get("source_version_ids") or []),
        history_messages=_parse_history_messages(body.get("history")),
        model_id=_resolve_model_id(body.get("model_id")),
        max_tool_rounds=3,
        tool_metadata={
            "owner_id": owner_id,
            "course_id": str(course_summary.get("course_id") or course_id),
            "course_session_id": str(course_context.get("course_session_id") or ""),
            "course_title": course_summary.get("title") or "当前课程",
            "current_task_id": body.get("current_task_id"),
            "current_source_version_id": body.get("current_source_version_id"),
            "allowed_source_version_ids": list(course_context.get("source_version_ids") or []),
            "learning_context": course_context.get("learning_context") or {},
            "mention_context": course_context.get("mention_context") or {},
            "course_summary": course_summary,
            "chat_intent": tool_access.chat_intent.value,
            "allow_retrieval": tool_access.allow_retrieval,
            "allow_progress": tool_access.allow_progress,
            "intent_reason": tool_access.reason,
        },
    )


@extend_schema(
    summary="列出课程 Agent 会话",
    tags=["课程 Agent"],
)
@api_view(["GET"])
def course_agent_session_list(request, course_id):
    """GET /api/courses/<course_id>/agent-sessions/"""
    from mentora.courses.models import Course
    if not Course.objects.filter(id=course_id, owner=request.user).exists():
        return Response({"error": "课程不存在"}, status=404)
    try:
        limit = max(1, min(100, int(request.GET.get("limit", 20))))
    except (ValueError, TypeError):
        limit = 20

    sessions = (
        CourseAgentSession.objects.filter(
            course_id=course_id,
            owner=request.user,
            status=CourseAgentSession.Status.ACTIVE,
        )
        .prefetch_related("messages")
        .order_by("-updated_at")[:limit]
    )
    return Response({
        "course_id": str(course_id),
        "items": [serialize_course_agent_session_summary(s) for s in sessions],
    })


@extend_schema(
    summary="读取课程 Agent 会话详情",
    tags=["课程 Agent"],
)
@api_view(["GET"])
def course_agent_session_detail(request, course_id, session_id):
    """GET /api/courses/<course_id>/agent-sessions/<session_id>/"""
    try:
        session = CourseAgentSession.objects.prefetch_related("messages").get(
            id=session_id,
            course_id=course_id,
            owner=request.user,
        )
    except CourseAgentSession.DoesNotExist:
        return Response({"error": "会话不存在"}, status=404)

    return Response(serialize_course_agent_session_detail(session))


@extend_schema(
    summary="课程 Agent 流式对话",
    tags=["课程 Agent"],
)
@rate_limit("course_chat_stream", max_attempts=5, window_seconds=60)
@api_view(["POST"])
def course_agent_stream(request, course_id):
    """POST /api/courses/<course_id>/agent-sessions/stream/"""
    if not settings.LLM_API_KEY:
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': 'LLM_API_KEY 未配置'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=503,
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': '无效 JSON'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=400,
        )

    user_message = body.get("message", "").strip()
    if not user_message:
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': 'message 不能为空'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=400,
        )

    from mentora.courses.models import Course
    try:
        Course.objects.get(id=course_id, owner=request.user)
    except Course.DoesNotExist:
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': '课程不存在'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=404,
        )

    try:
        course_context = build_course_agent_context(
            course_id=str(course_id),
            current_source_version_id=body.get("current_source_version_id"),
            current_task_id=body.get("current_task_id"),
            mentions=body.get("mentions"),
        )
    except ValueError as exc:
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=404,
        )

    agent_session_id = body.get("agent_session_id")
    session_created = False
    session: CourseAgentSession | None = None

    if agent_session_id:
        try:
            session = CourseAgentSession.objects.get(
                id=agent_session_id,
                course_id=course_id,
                owner=request.user,
            )
        except CourseAgentSession.DoesNotExist:
            return StreamingHttpResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': '会话不存在'}, ensure_ascii=False)}\n\n"]),
                content_type="text/event-stream",
                status=404,
            )
    else:
        session = CourseAgentSession.objects.create(
            course_id=course_id,
            course_session_id=course_context["course_session_id"],
            owner=request.user,
            title=_session_title_from_message(user_message),
            status=CourseAgentSession.Status.ACTIVE,
        )
        session_created = True

    assert session is not None

    user_metadata = {}
    mentions = body.get("mentions")
    if isinstance(mentions, list):
        user_metadata["mentions"] = mentions

    CourseAgentMessage.objects.create(
        session=session,
        role=CourseAgentMessage.Role.USER,
        content=user_message,
        metadata_json=user_metadata,
    )
    session.updated_at = timezone.now()
    session.save(update_fields=["updated_at"])

    history = _load_session_history(session)
    body_with_history = {**body, "history": [{"role": m.role, "content": m.content} for m in history[:-1]]}
    task = _build_course_chat_task(
        body=body_with_history,
        course_id=str(course_id),
        course_context=course_context,
        owner_id=str(request.user.id),
    )
    if task is None:
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': 'message 不能为空'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=400,
        )

    orch = _ensure_runtime()

    def sync_event_stream():
        assistant_content: list[str] = []
        assistant_citations: list[dict] = []
        stream_error: str | None = None
        stream_completed = False

        if session_created:
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "session_created",
                        "session_id": str(session.id),
                        "title": session.title,
                        "course_id": str(course_id),
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        loop = asyncio.new_event_loop()
        agen = orch.run_stream(task)
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(agen.__anext__())
                    if chunk.startswith("data: "):
                        try:
                            payload = json.loads(chunk[6:].strip())
                            if payload.get("type") == "chunk":
                                assistant_content.append(payload.get("content") or "")
                            elif payload.get("type") == "citations":
                                citations = payload.get("citations")
                                if isinstance(citations, list):
                                    assistant_citations.extend(citations)
                            elif payload.get("type") == "error":
                                stream_error = payload.get("message") or "未知错误"
                            elif payload.get("type") == "done":
                                stream_completed = True
                        except json.JSONDecodeError:
                            pass
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

        if stream_completed and not stream_error and assistant_content:
            with transaction.atomic():
                CourseAgentMessage.objects.create(
                    session=session,
                    role=CourseAgentMessage.Role.ASSISTANT,
                    content="".join(assistant_content),
                    citations_json=assistant_citations,
                )
                session.updated_at = timezone.now()
                session.save(update_fields=["updated_at"])

    return StreamingHttpResponse(
        sync_event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
