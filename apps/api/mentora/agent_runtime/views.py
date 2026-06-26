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

    task = OrchestratorTask(
        id=f"chat-{uuid.uuid4().hex[:12]}",
        mode="single",
        agent_role="tutor",
        user_message=user_message,
        context_sources=[],
        max_tool_rounds=3,
    )

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

    task = OrchestratorTask(
        id=f"chat-{uuid.uuid4().hex[:12]}",
        mode="single",
        agent_role="tutor",
        user_message=user_message,
        context_sources=[],
        max_tool_rounds=3,
    )

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
