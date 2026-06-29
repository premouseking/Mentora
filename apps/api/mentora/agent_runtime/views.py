"""
Agent Runtime HTTP 视图：聊天 API（非流式 + 流式 SSE）。

约定：
- POST /api/chat/ 接收 { message, history? } 返回 { reply, status }
- POST /api/chat/stream/ 接收 { message, history? } 返回 SSE 事件流
- 使用 runtime 工厂统一初始化 Orchestrator

约束：
- LLM_API_KEY 未配置时返回 503

@module mentora/agent_runtime/views
"""

import asyncio
import json
import uuid

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.agent_runtime.runtime import build_orchestrator
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.schemas import Message
from mentora.agent_runtime.prompts.manager import PromptManager

_orchestrator = None
_gateway: ModelGateway | None = None
_prompt_manager: PromptManager | None = None


def _ensure_runtime():
    global _orchestrator, _gateway, _prompt_manager
    if _orchestrator is None:
        _orchestrator, _gateway, _prompt_manager = build_orchestrator()
    return _orchestrator


def get_gateway() -> ModelGateway:
    """获取单例 ModelGateway（供 courses 等模块复用）。"""
    _ensure_runtime()
    assert _gateway is not None
    return _gateway


def get_prompt_manager() -> PromptManager:
    """获取单例 PromptManager。"""
    _ensure_runtime()
    assert _prompt_manager is not None
    return _prompt_manager


def _parse_history_messages(raw_history) -> list[Message]:
    if not isinstance(raw_history, list):
        return []

    messages: list[Message] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        messages.append(Message(role=role, content=content))
    return messages[-20:]


def _format_attachment_summary(raw_attachments) -> str:
    if not isinstance(raw_attachments, list):
        return ""

    lines: list[str] = []
    for item in raw_attachments[:10]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "unnamed").strip()[:120]
        kind = "image" if item.get("kind") == "image" else "file"
        mime_type = str(item.get("mime_type") or "application/octet-stream").strip()[:80]
        size = item.get("size")
        size_text = f", {size} bytes" if isinstance(size, int) and size >= 0 else ""
        label = "image" if kind == "image" else "file"
        lines.append(f"- {label}: {name} ({mime_type}{size_text})")

    if not lines:
        return ""
    return "\n\nAttached files provided by the user:\n" + "\n".join(lines)


def _resolve_model_id(raw_model_id) -> str | None:
    model_key = raw_model_id.strip().lower() if isinstance(raw_model_id, str) else "auto"
    if model_key == "fast":
        return getattr(settings, "LLM_MODEL_FAST", None)
    if model_key == "premium":
        return getattr(settings, "LLM_MODEL_PREMIUM", None)
    return getattr(settings, "LLM_MODEL_BALANCED", None)


def _build_chat_task(body: dict) -> OrchestratorTask | None:
    user_message = body.get("message", "").strip()
    if not user_message:
        return None

    user_message += _format_attachment_summary(body.get("attachments"))
    return OrchestratorTask(
        id=f"chat-{uuid.uuid4().hex[:12]}",
        mode="single",
        agent_role="tutor",
        user_message=user_message,
        context_sources=[],
        history_messages=_parse_history_messages(body.get("history")),
        model_id=_resolve_model_id(body.get("model_id")),
        max_tool_rounds=3,
    )


@api_view(["POST"])
@extend_schema(summary="Chat Api")
def chat_api(request):
    """POST /api/chat/"""
    if not settings.LLM_API_KEY:
        return Response(
            {"error": "LLM_API_KEY 未配置，请在 .env 中设置"},
            status=503,
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response({"error": "无效 JSON"}, status=400)

    user_message = body.get("message", "").strip()
    if not user_message:
        return Response({"error": "message 不能为空"}, status=400)

    task = _build_chat_task(body)
    assert task is not None

    try:
        orch = _ensure_runtime()
        result = asyncio.run(orch.run(task))
        reply = result.final_output.final_message if result.final_output else ""

        return Response({
            "reply": reply,
            "status": result.status,
            "usage": (
                result.final_output.usage.model_dump()
                if result.final_output
                else {}
            ),
        })
    except Exception as exc:
        return Response({
            "reply": "",
            "status": "failed",
            "error": str(exc),
        }, status=500)


@api_view(["POST"])
@extend_schema(summary="Chat Stream")
def chat_stream(request):
    """POST /api/chat/stream/"""
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

    task = _build_chat_task(body)
    assert task is not None

    orch = _ensure_runtime()

    def sync_event_stream():
        loop = asyncio.new_event_loop()
        agen = orch.run_stream(task)
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(agen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return StreamingHttpResponse(
        sync_event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
