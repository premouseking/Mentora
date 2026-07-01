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
import logging
from typing import TYPE_CHECKING

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.models import SubAgentRun
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

log = logging.getLogger(__name__)
_run_manager = None


def _get_run_manager():
    global _run_manager
    if _run_manager is None:
        from mentora.agent_runtime.services import RunManager
        _run_manager = RunManager()
    return _run_manager


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
    audit_sub_agent_run_id: str = "",
    emitter: EventEmitter | None,
) -> tuple[ToolInvocationRecord, str, list[dict]]:
    """执行单个工具调用，返回 (记录, tool message 内容, 引文列表)。"""
    try:
        args = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        args = {}

    if emitter:
        emitter.tool_call(task_id, tc.function.name, args)

    ctx = ToolContext(
        task_id=task_id,
        agent_role=agent_role,
        run_id=audit_sub_agent_run_id,
    )
    result = await registry.execute(tc.function.name, args, ctx)
    content = _format_tool_message_content(result)
    citations = _extract_tool_citations(result)

    if audit_sub_agent_run_id:
        try:
            sub_run = SubAgentRun.objects.get(id=audit_sub_agent_run_id)
            tool_result = result.result if isinstance(result.result, dict) else {"value": result.result}
            _get_run_manager().record_tool_invocation(
                sub_run,
                tc.function.name,
                args,
                result=tool_result,
                success=result.success,
                duration_ms=result.duration_ms,
                artifact_ref=result.artifact_ref or "",
            )
        except SubAgentRun.DoesNotExist:
            log.warning("audit sub_agent_run not found: %s", audit_sub_agent_run_id)

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
            details={"citations": citations},
        )

    return record, content, citations


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
) -> AgentOutput:
    """非流式多轮 tool loop。"""
    total_usage = TokenUsage()
    tool_records: list[ToolInvocationRecord] = []
    all_citations: list[Citation] = []
    chat_messages = list(agent_input.context.messages)
    tools = registry.get_openai_tools(agent_role)

    for _round_num in range(agent_input.max_tool_rounds):
        resp = await gateway.chat(
            task_type=agent_role,
            messages=chat_messages,
            tools=tools or None,
            model=agent_input.model_id,
        )
        total_usage = _merge_usage(total_usage, resp.usage)

        if not resp.tool_calls:
            return AgentOutput(
                agent_role=agent_role,
                task_id=agent_input.task_id,
                final_message=resp.content or "",
                citations=all_citations,
                tool_calls_made=tool_records,
                finish_reason="completed",
                usage=total_usage,
            )

        chat_messages.append(_build_assistant_message(resp))
        for tc in resp.tool_calls:
            record, content, citations = await _execute_tool(
                registry,
                tc,
                task_id=agent_input.task_id,
                agent_role=agent_role,
                audit_sub_agent_run_id=agent_input.audit_sub_agent_run_id,
                emitter=emitter,
            )
            tool_records.append(record)
            for c in citations:
                all_citations.append(Citation(
                    evidence_id=c.get("evidence_id", ""),
                    content_preview=c.get("content_preview", ""),
                    page_number=c.get("page_number"),
                ))
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
        citations=all_citations,
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
) -> AgentOutput:
    """流式多轮 tool loop；内容 chunk 通过 emitter 推送。"""
    total_usage = TokenUsage()
    tool_records: list[ToolInvocationRecord] = []
    all_citations: list[Citation] = []
    chat_messages = list(agent_input.context.messages)
    tools = registry.get_openai_tools(agent_role)

    round_num = 0
    while round_num < agent_input.max_tool_rounds:
        round_num += 1
        if emitter:
            emitter.agent_thinking(agent_input.task_id, round_num)

        accumulated_content: list[str] = []
        pending_tool_calls: list[ToolCall] = []

        async for chunk in gateway.chat_stream(
            task_type=agent_role,
            messages=chat_messages,
            tools=tools or None,
            model=agent_input.model_id,
        ):
            total_usage = _merge_usage(total_usage, chunk.usage)
            # 部分 Provider 会在 finish chunk 重复携带完整 tool_calls，按最后一次覆盖即可。
            if chunk.tool_calls:
                pending_tool_calls = list(chunk.tool_calls)
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
            return AgentOutput(
                agent_role=agent_role,
                task_id=agent_input.task_id,
                final_message=full_content,
                citations=all_citations,
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
            record, content, citations = await _execute_tool(
                registry,
                tc,
                task_id=agent_input.task_id,
                agent_role=agent_role,
                audit_sub_agent_run_id=agent_input.audit_sub_agent_run_id,
                emitter=emitter,
            )
            tool_records.append(record)
            for c in citations:
                all_citations.append(Citation(
                    evidence_id=c.get("evidence_id", ""),
                    content_preview=c.get("content_preview", ""),
                    page_number=c.get("page_number"),
                ))
            chat_messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

    # 轮次用尽仍未产出最终文本时，再尝试一次无工具补全，避免对话戛然而止。
    fallback_content: list[str] = []
    try:
        async for chunk in gateway.chat_stream(
            task_type=agent_role,
            messages=chat_messages,
            tools=None,
            model=agent_input.model_id,
        ):
            total_usage = _merge_usage(total_usage, chunk.usage)
            if chunk.content:
                fallback_content.append(chunk.content)
                if emitter:
                    emitter.agent_response_stream(
                        agent_input.task_id, chunk.content, is_final=False
                    )
    except Exception:
        log.warning("max-rounds fallback stream failed", exc_info=True)
        if emitter:
            emitter.agent_run_error(
                agent_input.task_id,
                agent_role,
                "fallback_stream_error",
                "补全回复失败",
            )

    final_message = "".join(fallback_content)
    if emitter and final_message:
        emitter.agent_response_stream(agent_input.task_id, "", is_final=True)

    return AgentOutput(
        agent_role=agent_role,
        task_id=agent_input.task_id,
        final_message=final_message,
        citations=all_citations,
        tool_calls_made=tool_records,
        finish_reason="completed" if final_message else "max_rounds",
        usage=total_usage,
    )
