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
import re
from typing import TYPE_CHECKING

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
from mentora.model_gateway.dsml_tool_calls import DsmlStreamFilter, parse_dsml_tool_calls
from mentora.model_gateway.schemas import ChatResponse, Message, ToolCall

if TYPE_CHECKING:
    from mentora.agent_runtime.events import EventEmitter

RETRIEVAL_TOOL_NAMES = frozenset({"retrieve_evidence"})
PROGRESS_TOOL_NAMES = frozenset({"get_learning_progress"})

_FINAL_ANSWER_NUDGE = (
    "工具已不可用。请直接基于上文 tool message 中的检索结果给出完整、准确的中文回答。"
    "禁止输出 DSML 或再次请求检索。"
)
_RETRIEVAL_PREAMBLE = re.compile(
    r"^(再)?(补充)?(让我|我来)?.*(检索|查一下|查|再找)",
    re.IGNORECASE,
)
_ANSWER_MARKERS = re.compile(
    r"(是|指|负责|包括|所谓|概念|用于|作用|功能|主要|核心|管理|调度|进程|内存|文件系统).+",
    re.IGNORECASE,
)


def _filter_tools_for_turn(
    tools: list[dict],
    tool_metadata: dict | None,
) -> list[dict]:
    """按意图门控过滤本轮可见工具。"""
    if not tools:
        return tools

    metadata = tool_metadata or {}
    allow_retrieval = metadata.get("allow_retrieval", True)
    allow_progress = metadata.get("allow_progress", True)

    filtered: list[dict] = []
    for tool in tools:
        function = tool.get("function") or {}
        name = str(function.get("name") or "")
        if name in RETRIEVAL_TOOL_NAMES and not allow_retrieval:
            continue
        if name in PROGRESS_TOOL_NAMES and not allow_progress:
            continue
        filtered.append(tool)
    return filtered


def _merge_usage(total: TokenUsage, addition: TokenUsage | None) -> TokenUsage:
    if addition is None:
        return total
    return TokenUsage(
        prompt_tokens=total.prompt_tokens + addition.prompt_tokens,
        completion_tokens=total.completion_tokens + addition.completion_tokens,
        total_tokens=total.total_tokens + addition.total_tokens,
    )


def _sanitize_tool_result_for_model(tool_name: str, value):
    """隐藏内部证据 ID，只把模型回答需要的证据正文交给模型。"""
    if tool_name == "retrieve_evidence" and isinstance(value, dict):
        sanitized = {
            "query": value.get("query", ""),
            "total_candidates": value.get("total_candidates", 0),
            "elapsed_ms": value.get("elapsed_ms", 0),
            "results": [],
        }
        for item in value.get("results", []):
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("text") or item.get("content_preview") or ""
            sanitized_item = {
                "content": str(content).strip(),
                "content_preview": str(item.get("content_preview") or content).strip(),
                "page_number": item.get("page_number", item.get("page")),
            }
            if item.get("source_title"):
                sanitized_item["source_title"] = item["source_title"]
            sanitized["results"].append(sanitized_item)
        return sanitized

    if isinstance(value, dict):
        return {
            key: _sanitize_tool_result_for_model(tool_name, item)
            for key, item in value.items()
            if key != "evidence_id"
        }
    if isinstance(value, list):
        return [_sanitize_tool_result_for_model(tool_name, item) for item in value]
    return value


def _format_tool_message_content(result) -> str:
    """将 ToolResult 格式化为模型可读的 tool message 内容。"""
    payload = {
        "success": result.success,
        "result": _sanitize_tool_result_for_model(result.tool_name, result.result),
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
        content = item.get("content") or item.get("text") or item.get("content_preview") or ""
        preview = item.get("content_preview") or content
        page_number = item.get("page_number", item.get("page"))
        citation = {
            "content": str(content).strip(),
            "content_preview": str(preview).strip()[:240],
            "page_number": page_number,
        }
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
    tool_metadata: dict | None = None,
) -> tuple[ToolInvocationRecord, str, list[dict]]:
    """执行单个工具调用，返回 (记录, tool message 内容, 引文列表)。"""
    try:
        args = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        args = {}

    if emitter:
        emitter.tool_call(task_id, tc.function.name, args)

    metadata = tool_metadata or {}
    ctx = ToolContext(
        task_id=task_id,
        agent_role=agent_role,
        run_id="",
        owner_id=str(metadata.get("owner_id") or ""),
        course_id=metadata.get("course_id"),
        metadata=metadata,
    )
    result = await registry.execute(tc.function.name, args, ctx)
    content = _format_tool_message_content(result)
    citations = _extract_tool_citations(result)

    record = ToolInvocationRecord(
        tool_name=tc.function.name,
        arguments=args,
        success=result.success,
        duration_ms=result.duration_ms,
        result=result.result if isinstance(result.result, dict) else None,
        error=result.error or "",
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


def _resolve_round_tools(
    tools: list[dict],
    *,
    round_num: int,
    max_tool_rounds: int,
    tool_records: list[ToolInvocationRecord],
) -> list[dict] | None:
    """检索完成后禁止再次 tool call，最后一轮也禁止。"""
    del round_num, max_tool_rounds, tool_records
    return tools or None


def _resolve_content_and_tool_calls(
    raw_content: str,
    tool_calls: list[ToolCall],
    *,
    allow_tool_calls: bool,
) -> tuple[str, list[ToolCall]]:
    """兼容 DeepSeek DSML：从 content 提取 tool call 并剥离可见文本。"""
    if not allow_tool_calls:
        cleaned, _ = parse_dsml_tool_calls(raw_content, allow_promotion=False)
        return cleaned or "", []

    if tool_calls:
        cleaned, _ = parse_dsml_tool_calls(raw_content)
        return cleaned or "", tool_calls
    cleaned, dsml_calls = parse_dsml_tool_calls(raw_content)
    return cleaned or "", dsml_calls


def _needs_final_answer_fallback(content: str, *, allow_tool_calls: bool) -> bool:
    """工具禁用轮若只剩检索前导语或空内容，需强制正文兜底。"""
    if allow_tool_calls:
        return False
    stripped = (content or "").strip()
    if not stripped:
        return True
    if _ANSWER_MARKERS.search(stripped):
        return False
    return len(stripped) <= 40 and bool(_RETRIEVAL_PREAMBLE.search(stripped))


async def _maybe_force_final_answer(
    *,
    gateway: ModelGateway,
    agent_role: str,
    agent_input: AgentInput,
    chat_messages: list[Message],
    content: str,
    usage: TokenUsage,
    allow_tool_calls: bool,
) -> tuple[str, TokenUsage]:
    if not _needs_final_answer_fallback(content, allow_tool_calls=allow_tool_calls):
        return content, usage

    fallback_messages = [
        *chat_messages,
        Message(role="user", content=_FINAL_ANSWER_NUDGE),
    ]
    fallback_resp = await gateway.chat(
        task_type=agent_role,
        messages=fallback_messages,
        tools=None,
        model=agent_input.model_id,
    )
    fallback_content, _ = _resolve_content_and_tool_calls(
        fallback_resp.content or "",
        list(fallback_resp.tool_calls or []),
        allow_tool_calls=False,
    )
    merged_usage = _merge_usage(usage, fallback_resp.usage)
    return fallback_content or content, merged_usage


async def _run_stream_model_round(
    *,
    gateway: ModelGateway,
    agent_role: str,
    agent_input: AgentInput,
    chat_messages: list[Message],
    round_tools: list[dict] | None,
    emitter: EventEmitter | None,
) -> tuple[TokenUsage, str, list[ToolCall]]:
    visible_content: list[str] = []
    raw_content: list[str] = []
    pending_tool_calls: list[ToolCall] = []
    round_usage = TokenUsage()
    dsml_filter = DsmlStreamFilter()

    try:
        async for chunk in gateway.chat_stream(
            task_type=agent_role,
            messages=chat_messages,
            tools=round_tools,
            model=agent_input.model_id,
        ):
            round_usage = _merge_usage(round_usage, chunk.usage)
            if chunk.tool_calls:
                pending_tool_calls.extend(chunk.tool_calls)
            if chunk.content:
                raw_content.append(chunk.content)
                visible_content.extend(dsml_filter.push(chunk.content))
    except Exception:
        # SSE 中断但 tool call 已完整收到时，仍继续执行工具链
        if not pending_tool_calls:
            raise

    allow_tool_calls = round_tools is not None
    full_raw = "".join(raw_content)
    full_visible, resolved_calls = _resolve_content_and_tool_calls(
        full_raw,
        pending_tool_calls,
        allow_tool_calls=allow_tool_calls,
    )
    pending_tool_calls = resolved_calls

    if not pending_tool_calls:
        visible_content.extend(dsml_filter.flush())
        for visible in visible_content:
            if emitter:
                emitter.agent_response_stream(
                    agent_input.task_id, visible, is_final=False
                )
        if emitter:
            emitter.agent_response_stream(agent_input.task_id, "", is_final=True)

    return round_usage, full_visible, pending_tool_calls


async def _run_blocking_model_round(
    *,
    gateway: ModelGateway,
    agent_role: str,
    agent_input: AgentInput,
    chat_messages: list[Message],
    round_tools: list[dict] | None,
    emitter: EventEmitter | None,
) -> tuple[TokenUsage, str, list[ToolCall]]:
    """检索后改用非流式，避免 SSE 中断导致无正文。"""
    allow_tool_calls = round_tools is not None
    resp = await gateway.chat(
        task_type=agent_role,
        messages=chat_messages,
        tools=round_tools,
        model=agent_input.model_id,
    )
    content, tool_calls = _resolve_content_and_tool_calls(
        resp.content or "",
        list(resp.tool_calls or []),
        allow_tool_calls=allow_tool_calls,
    )
    round_usage = resp.usage or TokenUsage()

    if not tool_calls:
        content, round_usage = await _maybe_force_final_answer(
            gateway=gateway,
            agent_role=agent_role,
            agent_input=agent_input,
            chat_messages=chat_messages,
            content=content,
            usage=round_usage,
            allow_tool_calls=allow_tool_calls,
        )

    if content and emitter:
        emitter.agent_response_stream(agent_input.task_id, content, is_final=False)
    if emitter:
        emitter.agent_response_stream(agent_input.task_id, "", is_final=True)
    return (
        round_usage,
        content,
        tool_calls,
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
    tools = _filter_tools_for_turn(
        registry.get_openai_tools(agent_role),
        agent_input.tool_metadata,
    )

    for round_num in range(agent_input.max_tool_rounds):
        round_tools = _resolve_round_tools(
            tools,
            round_num=round_num,
            max_tool_rounds=agent_input.max_tool_rounds,
            tool_records=tool_records,
        )

        resp = await gateway.chat(
            task_type=agent_role,
            messages=chat_messages,
            tools=round_tools,
            model=agent_input.model_id,
        )
        total_usage = _merge_usage(total_usage, resp.usage)

        allow_tool_calls = round_tools is not None
        content, tool_calls = _resolve_content_and_tool_calls(
            resp.content or "",
            list(resp.tool_calls or []),
            allow_tool_calls=allow_tool_calls,
        )

        if not tool_calls:
            content, total_usage = await _maybe_force_final_answer(
                gateway=gateway,
                agent_role=agent_role,
                agent_input=agent_input,
                chat_messages=chat_messages,
                content=content,
                usage=total_usage,
                allow_tool_calls=allow_tool_calls,
            )
            return AgentOutput(
                agent_role=agent_role,
                task_id=agent_input.task_id,
                final_message=content,
                citations=all_citations,
                tool_calls_made=tool_records,
                finish_reason="completed",
                usage=total_usage,
            )

        chat_messages.append(
            Message(
                role="assistant",
                content=content or None,
                tool_calls=tool_calls,
            )
        )
        for tc in tool_calls:
            record, content, citations = await _execute_tool(
                registry,
                tc,
                task_id=agent_input.task_id,
                agent_role=agent_role,
                emitter=emitter,
                tool_metadata=agent_input.tool_metadata,
            )
            tool_records.append(record)
            for c in citations:
                all_citations.append(Citation(
                    content=c.get("content", ""),
                    content_preview=c.get("content_preview", ""),
                    page_number=c.get("page_number"),
                    source_title=c.get("source_title", ""),
                ))
            chat_messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

    final_resp = await gateway.chat(
        task_type=agent_role,
        messages=chat_messages,
        tools=None,
        model=agent_input.model_id,
    )
    total_usage = _merge_usage(total_usage, final_resp.usage)
    final_content, _ = _resolve_content_and_tool_calls(
        final_resp.content or "",
        list(final_resp.tool_calls or []),
        allow_tool_calls=False,
    )
    final_content, total_usage = await _maybe_force_final_answer(
        gateway=gateway,
        agent_role=agent_role,
        agent_input=agent_input,
        chat_messages=chat_messages,
        content=final_content,
        usage=total_usage,
        allow_tool_calls=False,
    )
    return AgentOutput(
        agent_role=agent_role,
        task_id=agent_input.task_id,
        final_message=final_content,
        citations=all_citations,
        tool_calls_made=tool_records,
        finish_reason="completed",
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
    tools = _filter_tools_for_turn(
        registry.get_openai_tools(agent_role),
        agent_input.tool_metadata,
    )

    for round_num in range(agent_input.max_tool_rounds):
        round_tools = _resolve_round_tools(
            tools,
            round_num=round_num,
            max_tool_rounds=agent_input.max_tool_rounds,
            tool_records=tool_records,
        )

        if tool_records:
            round_usage, full_content, pending_tool_calls = await _run_blocking_model_round(
                gateway=gateway,
                agent_role=agent_role,
                agent_input=agent_input,
                chat_messages=chat_messages,
                round_tools=round_tools,
                emitter=emitter,
            )
        else:
            round_usage, full_content, pending_tool_calls = await _run_stream_model_round(
                gateway=gateway,
                agent_role=agent_role,
                agent_input=agent_input,
                chat_messages=chat_messages,
                round_tools=round_tools,
                emitter=emitter,
            )

        total_usage = _merge_usage(total_usage, round_usage)

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
                emitter=emitter,
                tool_metadata=agent_input.tool_metadata,
            )
            tool_records.append(record)
            for c in citations:
                all_citations.append(Citation(
                    content=c.get("content", ""),
                    content_preview=c.get("content_preview", ""),
                    page_number=c.get("page_number"),
                    source_title=c.get("source_title", ""),
                ))
            chat_messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

    round_usage, final_content, _ = await _run_blocking_model_round(
        gateway=gateway,
        agent_role=agent_role,
        agent_input=agent_input,
        chat_messages=chat_messages,
        round_tools=None,
        emitter=emitter,
    )
    total_usage = _merge_usage(total_usage, round_usage)
    return AgentOutput(
        agent_role=agent_role,
        task_id=agent_input.task_id,
        final_message=final_content,
        citations=all_citations,
        tool_calls_made=tool_records,
        finish_reason="completed",
        usage=total_usage,
    )
