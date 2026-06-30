"""
统一 async tool loop：Agent 多轮工具调用循环。

约定：
- 唯一工具循环实现，TutorAgent / PlannerAgent 委托调用
- 调用 ModelGateway.chat / chat_stream，工具执行走 ToolRegistry.execute
- 工具结果 JSON 序列化后回填 tool message

约束：
- 不在 stream 过程中提前 dispatch tool；等完整 tool_calls 汇总后再执行
- emitter 可选，用于 SSE 内部事件

@module mentora/agent_runtime/agents/turn_loop
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.schemas.output import (
    AgentOutput,
    Citation,
    TokenUsage,
    ToolInvocationRecord,
)
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.schemas import ChatResponse, Message, ToolCall

if TYPE_CHECKING:
    from mentora.agent_runtime.events import EventEmitter


def _merge_usage(total: TokenUsage, addition: TokenUsage | None) -> TokenUsage:
    if addition is None:
        return total
    return TokenUsage(
        prompt_tokens=total.prompt_tokens + addition.prompt_tokens,
        completion_tokens=total.completion_tokens + addition.completion_tokens,
        total_tokens=total.total_tokens + addition.total_tokens,
    )


def _format_tool_message_content(result) -> str:
    """将 ToolResult 格式化为模型可读的 tool message 内容。"""
    payload = {
        "success": result.success,
        "result": result.result,
        "error": result.error,
    }
    if result.artifact_ref:
        payload["artifact_ref"] = result.artifact_ref
    return json.dumps(payload, ensure_ascii=False, default=str)


def _extract_tool_citations(result) -> list[dict]:
    if not result.success or not isinstance(result.result, dict):
        return []

    citations = []
    for item in result.result.get("results", []):
        if not isinstance(item, dict):
            continue
        preview = item.get("content_preview") or item.get("content") or item.get("text") or ""
        page_number = item.get("page_number", item.get("page"))
        citation = {
            "content_preview": str(preview)[:240],
            "page_number": page_number,
        }
        if item.get("evidence_id"):
            citation["evidence_id"] = item["evidence_id"]
        if item.get("source_title"):
            citation["source_title"] = item["source_title"]
        citations.append(citation)
    return citations


async def _execute_tool(
    registry: ToolRegistry,
    tc: ToolCall,
    *,
    task_id: str,
    agent_role: str,
    emitter: EventEmitter | None,
) -> tuple[ToolInvocationRecord, str]:
    """执行单个工具调用，返回记录与 tool message 内容。"""
    try:
        args = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        args = {}

    if emitter:
        emitter.tool_call(task_id, tc.function.name, args)

    ctx = ToolContext(task_id=task_id, agent_role=agent_role, run_id="")
    result = await registry.execute(tc.function.name, args, ctx)
    content = _format_tool_message_content(result)

    record = ToolInvocationRecord(
        tool_name=tc.function.name,
        arguments=args,
        success=result.success,
        duration_ms=result.duration_ms,
    )

    if emitter:
        preview = content[:200] if result.success else (result.error or content)[:200]
        emitter.tool_result(
            task_id,
            tc.function.name,
            result.success,
            preview,
            details={"citations": _extract_tool_citations(result)},
        )

    return record, content


def _build_assistant_message(resp: ChatResponse) -> Message:
    return Message(
        role="assistant",
        content=resp.content,
        tool_calls=resp.tool_calls,
    )


async def run_tool_loop(
    *,
    agent_role: str,
    agent_input: AgentInput,
    registry: ToolRegistry,
    gateway: ModelGateway,
    emitter: EventEmitter | None = None,
    extract_citations: Callable[[ChatResponse], list[Citation]] | None = None,
) -> AgentOutput:
    """非流式多轮 tool loop。"""
    total_usage = TokenUsage()
    tool_records: list[ToolInvocationRecord] = []
    chat_messages = list(agent_input.context.messages)
    tools = registry.get_openai_tools(agent_role)
    citations_fn = extract_citations or (lambda _resp: [])

    for _round_num in range(agent_input.max_tool_rounds):
        resp = await gateway.chat(
            task_type=agent_role,
            messages=chat_messages,
            tools=tools or None,
        )
        total_usage = _merge_usage(total_usage, resp.usage)

        if not resp.tool_calls:
            return AgentOutput(
                agent_role=agent_role,
                task_id=agent_input.task_id,
                final_message=resp.content or "",
                citations=citations_fn(resp),
                tool_calls_made=tool_records,
                finish_reason="completed",
                usage=total_usage,
            )

        chat_messages.append(_build_assistant_message(resp))
        for tc in resp.tool_calls:
            record, content = await _execute_tool(
                registry,
                tc,
                task_id=agent_input.task_id,
                agent_role=agent_role,
                emitter=emitter,
            )
            tool_records.append(record)
            chat_messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

    return AgentOutput(
        agent_role=agent_role,
        task_id=agent_input.task_id,
        final_message="",
        citations=[],
        tool_calls_made=tool_records,
        finish_reason="max_rounds",
        usage=total_usage,
    )


async def run_tool_loop_stream(
    *,
    agent_role: str,
    agent_input: AgentInput,
    registry: ToolRegistry,
    gateway: ModelGateway,
    emitter: EventEmitter | None = None,
    extract_citations: Callable[[ChatResponse], list[Citation]] | None = None,
) -> AgentOutput:
    """流式多轮 tool loop；内容 chunk 通过 emitter 推送。"""
    total_usage = TokenUsage()
    tool_records: list[ToolInvocationRecord] = []
    chat_messages = list(agent_input.context.messages)
    tools = registry.get_openai_tools(agent_role)
    citations_fn = extract_citations or (lambda _resp: [])

    for _round_num in range(agent_input.max_tool_rounds):
        accumulated_content: list[str] = []
        pending_tool_calls: list[ToolCall] = []

        async for chunk in gateway.chat_stream(
            task_type=agent_role,
            messages=chat_messages,
            tools=tools or None,
        ):
            total_usage = _merge_usage(total_usage, chunk.usage)
            if chunk.tool_calls:
                pending_tool_calls.extend(chunk.tool_calls)
            if chunk.content:
                accumulated_content.append(chunk.content)
                if emitter:
                    emitter.agent_response_stream(
                        agent_input.task_id, chunk.content, is_final=False
                    )

        full_content = "".join(accumulated_content)
        if emitter:
            emitter.agent_response_stream(agent_input.task_id, "", is_final=True)

        if not pending_tool_calls:
            final_resp = ChatResponse(content=full_content, usage=total_usage)
            return AgentOutput(
                agent_role=agent_role,
                task_id=agent_input.task_id,
                final_message=full_content,
                citations=citations_fn(final_resp),
                tool_calls_made=tool_records,
                finish_reason="completed",
                usage=total_usage,
            )

        chat_messages.append(
            _build_assistant_message(
                ChatResponse(content=full_content, tool_calls=pending_tool_calls)
            )
        )
        for tc in pending_tool_calls:
            record, content = await _execute_tool(
                registry,
                tc,
                task_id=agent_input.task_id,
                agent_role=agent_role,
                emitter=emitter,
            )
            tool_records.append(record)
            chat_messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

    return AgentOutput(
        agent_role=agent_role,
        task_id=agent_input.task_id,
        final_message="",
        citations=[],
        tool_calls_made=tool_records,
        finish_reason="max_rounds",
        usage=total_usage,
    )
