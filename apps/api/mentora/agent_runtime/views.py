"""
Agent Runtime HTTP 视图：聊天 API（非流式 + 流式 SSE）。

约定：
- POST /api/chat/ 接收 { message, history? } 返回 { reply, status }
- POST /api/chat/stream/ 接收 { message, history? } 返回 SSE 事件流
- 使用 Orchestrator + TutorAgent 处理请求
- 单例初始化 Orchestrator（Provider / Gateway / Agent 复用）

约束：
- LLM_API_KEY 未配置时返回 503
- retrieve_evidence 工具为占位，暂时不影响纯文本对话

@module mentora/agent_runtime/views
"""

import asyncio
import json
import uuid

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.agents.tutor import TutorAgent
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.task import BudgetConfig, OrchestratorTask
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.openai import OpenAIProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.structured_output import StructuredOutputValidator

# ── 单例 Orchestrator ──

_orchestrator: Orchestrator | None = None


def _build_orchestrator() -> Orchestrator:
    """构建 Orchestrator，注入 OpenAIProvider + TutorAgent。"""
    api_key = settings.LLM_API_KEY
    if not api_key:
        raise RuntimeError("LLM_API_KEY 未配置，无法初始化 OpenAIProvider")

    provider = OpenAIProvider(
        api_key=api_key,
        base_url=settings.LLM_API_BASE_URL,
        model=settings.LLM_MODEL,
    )

    router = TaskRouter(default_provider=provider)
    gateway = ModelGateway(router=router, audit_enabled=False)

    prompt_manager = PromptManager()
    tool_registry = ToolRegistry()

    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    budget = BudgetConfig()
    token_counter = TokenCounter()
    context_mgr = ContextManager(budget=budget, counter=token_counter)

    return Orchestrator(
        agent_map={"tutor": tutor},
        prompt_manager=prompt_manager,
        context_manager=context_mgr,
    )


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _build_orchestrator()
    return _orchestrator


# ── 视图 ──

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """
    POST /api/chat/

    请求体：
    {
        "message": "用户输入",
        "history": [{"role": "user", "content": "..."}, ...]  // 可选
    }

    返回：
    {
        "reply": "Agent 回复",
        "status": "completed" | "failed",
        "error": "..."  // 仅失败时
    }
    """
    if not settings.LLM_API_KEY:
        return JsonResponse(
            {"error": "LLM_API_KEY 未配置，请在 .env 中设置"},
            status=503,
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "无效 JSON"}, status=400)

    user_message = body.get("message", "").strip()
    if not user_message:
        return JsonResponse({"error": "message 不能为空"}, status=400)

    # 构建 OrchestratorTask
    task = OrchestratorTask(
        id=f"chat-{uuid.uuid4().hex[:12]}",
        mode="single",
        agent_role="tutor",
        user_message=user_message,
        context_sources=[],
        max_tool_rounds=3,
    )

    try:
        import asyncio

        orch = _get_orchestrator()
        result = asyncio.run(orch.run(task))

        reply = result.final_output.final_message if result.final_output else ""

        return JsonResponse({
            "reply": reply,
            "status": result.status,
            "usage": (
                result.final_output.usage.model_dump()
                if result.final_output
                else {}
            ),
        })

    except Exception as exc:
        return JsonResponse({
            "reply": "",
            "status": "failed",
            "error": str(exc),
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def chat_stream(request):
    """
    POST /api/chat/stream/

    请求体与非流式相同，返回 SSE 事件流：

    data: {"type":"chunk","content":"..."}
    data: {"type":"done"}
    data: {"type":"error","message":"..."}

    前端通过 fetch + ReadableStream 消费。

    约束：
    - 同步视图，内建 event loop 桥接异步 run_stream 生成器
    - WSGI 模式下异步 StreamingHttpResponse 会被缓冲，因此手动迭代
    """
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

    orch = _get_orchestrator()

    def sync_event_stream():
        """同步生成器：内建 event loop 逐 chunk 从异步生成器拉取。"""
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
