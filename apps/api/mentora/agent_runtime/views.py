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

from mentora.agent_runtime.models import OrchestratorRun
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


@extend_schema(
    summary="AI 聊天（非流式）",
    description="发送消息给 AI 助教，返回完整回复。TutorAgent 会在必要时检索资料后回答。",
    tags=["Agent 聊天"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息正文"},
                "history": {
                    "type": "array",
                    "description": "历史对话消息列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["user", "assistant"]},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["message"],
        },
    },
    responses={
        200: {
            "description": "回复成功",
            "content": {
                "application/json": {
                    "type": "object",
                    "properties": {
                        "reply": {"type": "string", "description": "AI 回复正文"},
                        "status": {"type": "string", "enum": ["completed", "failed"]},
                        "usage": {
                            "type": "object",
                            "description": "Token 用量",
                            "properties": {
                                "prompt_tokens": {"type": "integer"},
                                "completion_tokens": {"type": "integer"},
                                "total_tokens": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
        400: {"description": "请求参数无效（message 为空或 JSON 格式错误）"},
        500: {"description": "Agent 运行异常"},
        503: {"description": "LLM_API_KEY 未配置"},
    },
)
@api_view(["POST"])
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


@extend_schema(
    summary="AI 聊天（流式 SSE）",
    description="发送消息给 AI 助教，通过 Server-Sent Events 流式返回回复内容。事件类型包括 chunk/status/citations/error/done。",
    tags=["Agent 聊天"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息正文"},
                "history": {
                    "type": "array",
                    "description": "历史对话消息列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["user", "assistant"]},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["message"],
        },
    },
    responses={
        (200, "text/event-stream"): {"description": "SSE 事件流"},
        400: {"description": "请求参数无效"},
        503: {"description": "LLM_API_KEY 未配置"},
    },
)
@api_view(["POST"])
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


@extend_schema(
    summary="Agent 运行历史列表",
    description="返回编排运行历史记录，按时间倒序排列。支持分页参数。",
    tags=["Agent 审计"],
    parameters=[
        {
            "name": "limit",
            "in_": "query",
            "type": "integer",
            "description": "返回条数上限，默认 20",
        },
        {
            "name": "offset",
            "in_": "query",
            "type": "integer",
            "description": "偏移量，默认 0",
        },
    ],
    responses={
        200: {"description": "运行历史列表"},
    },
)
@api_view(["GET"])
def run_list(request):
    """GET /api/runs/"""
    try:
        limit = max(1, min(100, int(request.GET.get("limit", 20))))
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = max(0, int(request.GET.get("offset", 0)))
    except (ValueError, TypeError):
        offset = 0

    qs = OrchestratorRun.objects.order_by("-created_at")
    total = qs.count()
    runs = qs[offset : offset + limit]

    items = []
    for run in runs:
        sub_count = run.sub_runs.count()
        items.append({
            "id": str(run.id),
            "mode": run.mode,
            "agent_role": run.agent_role,
            "status": run.status,
            "total_duration_ms": run.total_duration_ms,
            "total_tool_calls": run.total_tool_calls,
            "sub_agent_count": sub_count,
            "error_code": run.error_code,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        })

    return Response({"total": total, "limit": limit, "offset": offset, "items": items})


@extend_schema(
    summary="Agent 运行详情",
    description="返回单次编排运行的完整信息，包含子 Agent 运行记录和工具调用记录。",
    tags=["Agent 审计"],
    responses={
        200: {"description": "运行详情"},
        404: {"description": "运行记录不存在"},
    },
)
@api_view(["GET"])
def run_detail(request, run_id):
    """GET /api/runs/<run_id>/"""
    try:
        run = OrchestratorRun.objects.prefetch_related(
            "sub_runs__tool_invocations"
        ).get(id=run_id)
    except OrchestratorRun.DoesNotExist:
        return Response({"error": "运行记录不存在"}, status=404)

    sub_runs = []
    for sub in run.sub_runs.all():
        tools = []
        for inv in sub.tool_invocations.all():
            tools.append({
                "id": str(inv.id),
                "tool_name": inv.tool_name,
                "arguments": inv.arguments,
                "result": inv.result,
                "success": inv.success,
                "duration_ms": inv.duration_ms,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            })

        sub_runs.append({
            "id": str(sub.id),
            "agent_role": sub.agent_role,
            "status": sub.status,
            "duration_ms": sub.duration_ms,
            "tool_rounds": sub.tool_rounds,
            "usage_json": sub.usage_json,
            "error_code": sub.error_code,
            "error_message": sub.error_message,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "completed_at": sub.completed_at.isoformat() if sub.completed_at else None,
            "tool_invocations": tools,
        })

    return Response({
        "id": str(run.id),
        "mode": run.mode,
        "agent_role": run.agent_role,
        "status": run.status,
        "task_input": run.task_input,
        "output_json": run.output_json,
        "total_duration_ms": run.total_duration_ms,
        "total_tool_calls": run.total_tool_calls,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "sub_runs": sub_runs,
    })
