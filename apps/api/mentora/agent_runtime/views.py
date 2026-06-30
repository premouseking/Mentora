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
import time
import uuid

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.decorators import rate_limit
from mentora.agent_runtime.models import OrchestratorRun
from mentora.agent_runtime.runtime import build_orchestrator
from mentora.agent_runtime.schemas.context import AgentContext
from mentora.agent_runtime.schemas.task import OrchestratorTask, PipelineStep
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
@rate_limit("chat", max_attempts=10, window_seconds=60)
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
@rate_limit("chat_stream", max_attempts=5, window_seconds=60)
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


@extend_schema(
    summary="Pipeline 编排（非流式）",
    description="按顺序执行多步 Agent 编排。每一步指定 agent_role、任务指令和输出键名，后续步骤可通过 input_from 引用前面步骤的输出。",
    tags=["Agent 聊天"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "pipeline_steps": {
                    "type": "array",
                    "description": "Pipeline 步骤列表，按顺序执行",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_role": {
                                "type": "string",
                                "enum": ["tutor", "clarifier", "planner", "assessor"],
                                "description": "Agent 角色",
                            },
                            "task_instruction": {"type": "string", "description": "步骤任务指令"},
                            "output_key": {"type": "string", "description": "输出键名，供后续步骤引用"},
                            "input_from": {"type": "string", "description": "引用前面步骤的 output_key（可选）"},
                            "max_tool_rounds": {"type": "integer", "description": "最大工具调用轮次，默认 5"},
                        },
                        "required": ["agent_role", "task_instruction", "output_key"],
                    },
                },
                "context_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "上下文资料版本 ID 列表",
                },
            },
            "required": ["pipeline_steps"],
        },
    },
    responses={
        200: {"description": "Pipeline 完整执行结果"},
        400: {"description": "参数无效"},
        500: {"description": "Pipeline 执行异常"},
        503: {"description": "LLM_API_KEY 未配置"},
    },
)
@rate_limit("pipeline", max_attempts=3, window_seconds=120)
@api_view(["POST"])
def pipeline_chat(request):
    """POST /api/chat/pipeline/"""
    if not settings.LLM_API_KEY:
        return Response(
            {"error": "LLM_API_KEY 未配置，请在 .env 中设置"},
            status=503,
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response({"error": "无效 JSON"}, status=400)

    steps_raw = body.get("pipeline_steps")
    if not steps_raw or not isinstance(steps_raw, list):
        return Response({"error": "pipeline_steps 必须是非空数组"}, status=400)

    context_sources = body.get("context_sources") or []
    if not isinstance(context_sources, list):
        return Response({"error": "context_sources 必须是数组"}, status=400)

    pipeline_steps = []
    for i, step in enumerate(steps_raw):
        try:
            pipeline_steps.append(
                PipelineStep(
                    agent_role=step["agent_role"],
                    task_instruction=step["task_instruction"],
                    output_key=step["output_key"],
                    input_from=step.get("input_from"),
                    max_tool_rounds=step.get("max_tool_rounds", 5),
                )
            )
        except (KeyError, TypeError) as e:
            return Response(
                {"error": f"pipeline_steps[{i}] 缺少必填字段: {e}"},
                status=400,
            )

    task = OrchestratorTask(
        id=f"pipeline-{uuid.uuid4().hex[:12]}",
        mode="pipeline",
        user_message="",
        context_sources=context_sources,
        max_tool_rounds=0,
        pipeline_steps=pipeline_steps,
    )

    try:
        orch = _ensure_runtime()
        result = asyncio.run(orch.run(task))

        steps = []
        for output in result.agent_outputs:
            steps.append({
                "agent_role": output.agent_role,
                "output_key": "",
                "finish_reason": output.finish_reason,
                "content_preview": output.final_message[:300],
                "full_content": output.final_message,
                "citations": [
                    {"evidence_id": c.evidence_id, "content_preview": c.content_preview, "page_number": c.page_number}
                    for c in output.citations
                ],
                "tool_calls_made": len(output.tool_calls_made),
                "usage": output.usage.model_dump(),
            })

        # 补填 output_key（从请求的 pipeline_steps 中获取）
        for si, step_resp in enumerate(steps):
            if si < len(pipeline_steps):
                step_resp["output_key"] = pipeline_steps[si].output_key

        return Response({
            "status": result.status,
            "steps": steps,
            "total_duration_ms": result.total_duration_ms,
            "total_tool_calls": result.total_tool_calls,
        })

    except Exception as exc:
        return Response({
            "status": "failed",
            "error": str(exc),
        }, status=500)


@extend_schema(
    summary="Pipeline 编排（流式 SSE）",
    description="按顺序执行多步 Agent 编排，每步完成后推送 SSE 事件。事件类型包括 step_started/step_completed/error/done。",
    tags=["Agent 聊天"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "pipeline_steps": {
                    "type": "array",
                    "description": "Pipeline 步骤列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_role": {
                                "type": "string",
                                "enum": ["tutor", "clarifier", "planner", "assessor"],
                            },
                            "task_instruction": {"type": "string"},
                            "output_key": {"type": "string"},
                            "input_from": {"type": "string"},
                            "max_tool_rounds": {"type": "integer"},
                        },
                        "required": ["agent_role", "task_instruction", "output_key"],
                    },
                },
                "context_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "上下文资料版本 ID 列表",
                },
            },
            "required": ["pipeline_steps"],
        },
    },
    responses={
        (200, "text/event-stream"): {"description": "Pipeline SSE 事件流"},
        400: {"description": "参数无效"},
        503: {"description": "LLM_API_KEY 未配置"},
    },
)
@api_view(["POST"])
def pipeline_chat_stream(request):
    """POST /api/chat/pipeline/stream/"""
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

    steps_raw = body.get("pipeline_steps")
    if not steps_raw or not isinstance(steps_raw, list):
        return StreamingHttpResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': 'pipeline_steps 必须是非空数组'}, ensure_ascii=False)}\n\n"]),
            content_type="text/event-stream",
            status=400,
        )

    context_sources = body.get("context_sources") or []
    if not isinstance(context_sources, list):
        context_sources = []

    pipeline_steps = []
    for i, step in enumerate(steps_raw):
        try:
            pipeline_steps.append(
                PipelineStep(
                    agent_role=step["agent_role"],
                    task_instruction=step["task_instruction"],
                    output_key=step["output_key"],
                    input_from=step.get("input_from"),
                    max_tool_rounds=step.get("max_tool_rounds", 5),
                )
            )
        except (KeyError, TypeError) as e:
            return StreamingHttpResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': f'pipeline_steps[{i}] 缺少必填字段: {e}'}, ensure_ascii=False)}\n\n"]),
                content_type="text/event-stream",
                status=400,
            )

    orch = _ensure_runtime()
    task_id = f"pipeline-{uuid.uuid4().hex[:12]}"

    def sync_event_stream():
        t0 = time.perf_counter()
        step_results: dict[str, str] = {}
        total_calls = 0
        loop = asyncio.new_event_loop()

        try:
            for i, step in enumerate(pipeline_steps):
                # 推送 step_started
                yield f"data: {json.dumps({'type': 'step_started', 'step_index': i, 'agent_role': step.agent_role, 'output_key': step.output_key}, ensure_ascii=False)}\n\n"

                try:
                    agent = orch._agents[step.agent_role]
                    user_msg = step.task_instruction
                    if step.input_from and step.input_from in step_results:
                        user_msg = f"{user_msg}\n\n上一步结果: {step_results[step.input_from]}"

                    system_prompt = orch._build_system_prompt(
                        agent,
                        OrchestratorTask(
                            id=task_id, mode="pipeline",
                            context_sources=context_sources,
                        ),
                    )
                    messages, _allocation = orch._context_mgr.build_messages(
                        system_prompt=system_prompt,
                        user_message=user_msg,
                    )
                    ctx = AgentContext(messages=messages, system_prompt=system_prompt, allocation=_allocation)
                    agent_input = AgentInput(
                        task_id=task_id,
                        user_message=user_msg,
                        context=ctx,
                        max_tool_rounds=step.max_tool_rounds,
                    )

                    output = loop.run_until_complete(agent.run(agent_input))
                    step_results[step.output_key] = output.final_message
                    total_calls += len(output.tool_calls_made)

                    yield f"data: {json.dumps({'type': 'step_completed', 'step_index': i, 'agent_role': step.agent_role, 'output_key': step.output_key, 'finish_reason': output.finish_reason, 'content_preview': output.final_message[:300], 'citations': [{'evidence_id': c.evidence_id, 'content_preview': c.content_preview, 'page_number': c.page_number} for c in output.citations], 'tool_calls_made': len(output.tool_calls_made), 'usage': output.usage.model_dump()}, ensure_ascii=False)}\n\n"

                except Exception as step_exc:
                    yield f"data: {json.dumps({'type': 'error', 'step_index': i, 'agent_role': step.agent_role, 'message': str(step_exc)}, ensure_ascii=False)}\n\n"
                    break

            duration = (time.perf_counter() - t0) * 1000
            yield f"data: {json.dumps({'type': 'done', 'task_id': task_id, 'status': 'completed', 'steps_completed': len(step_results), 'total_duration_ms': duration, 'total_tool_calls': total_calls}, ensure_ascii=False)}\n\n"

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
