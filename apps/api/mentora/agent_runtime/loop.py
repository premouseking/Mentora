"""
Agent 核心 tool-loop。

约定：
- 同步路径：gateway.complete → 有 tool_calls 则执行并回填 → 继续。
- 流式路径：gateway.stream → 产出 TOKEN_DELTA → DONE 后同样处理 tool_calls。
- 无 tool_calls 则 turn 结束；达到 max_iterations 则抛 MaxIterationsError。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
@module mentora/agent_runtime/loop
"""

from __future__ import annotations

from collections.abc import Iterator

from mentora.model_gateway.contracts import (
    ModelMessage,
    ModelRequest,
    Role,
    StreamEventType,
    TokenUsage,
)
from mentora.model_gateway.gateway import ModelGateway, get_gateway

from .context import ContextManager
from .contracts import (
    AgentConfig,
    AgentEvent,
    AgentEventType,
    AgentMessage,
    AgentResult,
    EventEmitter,
)
from .exceptions import MaxIterationsError
from .prompts.base import PROMPT_VERSION, build_base_instructions, build_contextual_fragment
from .prompts.fragments import PromptContext
from .tools.base import ToolContext
from .tools.registry import ToolRegistry


def _merge_usage(total: TokenUsage, addition: TokenUsage) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=total.prompt_tokens + addition.prompt_tokens,
        completion_tokens=total.completion_tokens + addition.completion_tokens,
        total_tokens=total.total_tokens + addition.total_tokens,
    )


def _build_prompt_context(
    *,
    registry: ToolRegistry,
    tool_context: ToolContext,
    dynamic_context: str,
) -> PromptContext:
    return PromptContext(
        dynamic_context=dynamic_context,
        course_id=tool_context.course_id,
        scope_revision_id=tool_context.scope_revision_id,
        owner_id=tool_context.owner_id or None,
        available_tool_names=registry.tool_names(),
    )


def _build_round_request(
    *,
    context: ContextManager,
    registry: ToolRegistry,
    config: AgentConfig,
    tool_context: ToolContext,
    dynamic_context: str,
) -> ModelRequest:
    prompt_version = config.prompt_version or PROMPT_VERSION
    prompt_ctx = _build_prompt_context(
        registry=registry,
        tool_context=tool_context,
        dynamic_context=dynamic_context,
    )
    instructions = build_base_instructions(prompt_version=prompt_version)
    contextual_fragment = build_contextual_fragment(context=prompt_ctx)
    messages = [
        ModelMessage(role=Role.SYSTEM, content=instructions),
    ]
    if contextual_fragment:
        messages.append(ModelMessage(role=Role.USER, content=contextual_fragment))
    messages.extend(context.for_prompt())
    return ModelRequest(
        task_type=config.task_type,
        messages=messages,
        quality_tier=config.quality_tier,
        tools=registry.specs(),
        tool_choice="auto",
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        metadata={"prompt_version": prompt_version},
    )


def _emit_tool_round(
    *,
    response_text: str,
    tool_calls: list,
    round_index: int,
    context: ContextManager,
    registry: ToolRegistry,
    tool_context: ToolContext,
    emit: EventEmitter | None,
) -> None:
    context.record(
        [
            AgentMessage(
                role=Role.ASSISTANT.value,
                content=response_text,
                tool_calls=tuple(tool_calls),
            )
        ]
    )

    tool_messages: list[AgentMessage] = []
    for call in tool_calls:
        if emit is not None:
            emit(
                AgentEvent(
                    type=AgentEventType.TOOL_CALL_BEGIN,
                    round_index=round_index,
                    tool_name=call.name,
                    tool_call_id=call.id,
                )
            )

        result = registry.dispatch(call, tool_context)
        tool_messages.append(
            AgentMessage(
                role=Role.TOOL.value,
                content=result.content,
                tool_call_id=call.id,
                name=call.name,
            )
        )

        if emit is not None:
            emit(
                AgentEvent(
                    type=AgentEventType.TOOL_CALL_END,
                    round_index=round_index,
                    tool_name=call.name,
                    tool_call_id=call.id,
                    text=result.content[:200],
                    error="tool_error" if result.is_error else None,
                )
            )

    context.record(tool_messages)


def _invoke_model_sync(
    gateway: ModelGateway,
    request: ModelRequest,
) -> tuple[str, str, TokenUsage, list]:
    response = gateway.complete(request)
    return (
        response.text,
        response.finish_reason,
        response.usage,
        list(response.tool_calls),
    )


def _invoke_model_stream(
    gateway: ModelGateway,
    request: ModelRequest,
    *,
    round_index: int,
    emit: EventEmitter | None,
) -> tuple[str, str, TokenUsage, list]:
    text = ""
    finish_reason = "stop"
    usage = TokenUsage()
    tool_calls: list = []

    for event in gateway.stream(request):
        if event.type == StreamEventType.DELTA and event.text:
            text += event.text
            if emit is not None:
                emit(
                    AgentEvent(
                        type=AgentEventType.TOKEN_DELTA,
                        round_index=round_index,
                        text=event.text,
                    )
                )
        elif event.type == StreamEventType.DONE and event.response is not None:
            text = event.response.text or text
            finish_reason = event.response.finish_reason
            usage = event.response.usage
            tool_calls = list(event.response.tool_calls)

    return text, finish_reason, usage, tool_calls


def _run_turn_loop(
    *,
    user_input: str,
    context: ContextManager,
    registry: ToolRegistry,
    config: AgentConfig,
    tool_context: ToolContext,
    dynamic_context: str = "",
    gateway: ModelGateway | None = None,
    emit: EventEmitter | None = None,
    stream: bool = False,
) -> AgentResult:
    gateway = gateway or get_gateway()
    context.record([AgentMessage(role=Role.USER.value, content=user_input)])

    total_usage = TokenUsage()
    last_finish_reason = "stop"

    for round_index in range(1, config.max_iterations + 1):
        context.maybe_compact()

        if emit is not None:
            emit(
                AgentEvent(
                    type=AgentEventType.ROUND_START,
                    round_index=round_index,
                )
            )

        request = _build_round_request(
            context=context,
            registry=registry,
            config=config,
            tool_context=tool_context,
            dynamic_context=dynamic_context,
        )

        if stream:
            response_text, finish_reason, usage, tool_calls = _invoke_model_stream(
                gateway,
                request,
                round_index=round_index,
                emit=emit,
            )
        else:
            response_text, finish_reason, usage, tool_calls = _invoke_model_sync(
                gateway,
                request,
            )

        total_usage = _merge_usage(total_usage, usage)
        last_finish_reason = finish_reason

        if tool_calls:
            _emit_tool_round(
                response_text=response_text,
                tool_calls=tool_calls,
                round_index=round_index,
                context=context,
                registry=registry,
                tool_context=tool_context,
                emit=emit,
            )
            continue

        context.record([AgentMessage(role=Role.ASSISTANT.value, content=response_text)])

        result = AgentResult(
            text=response_text,
            rounds=round_index,
            finish_reason=last_finish_reason,
            usage=total_usage,
            messages=context.history,
        )
        if emit is not None:
            emit(
                AgentEvent(
                    type=AgentEventType.TURN_END,
                    round_index=round_index,
                    text=response_text,
                )
            )
        return result

    if emit is not None:
        emit(
            AgentEvent(
                type=AgentEventType.ERROR,
                round_index=config.max_iterations,
                error="max_iterations_exceeded",
            )
        )
    raise MaxIterationsError(
        f"达到最大迭代次数 {config.max_iterations}，turn 终止"
    )


def run_turn(
    *,
    user_input: str,
    context: ContextManager,
    registry: ToolRegistry,
    config: AgentConfig,
    tool_context: ToolContext,
    dynamic_context: str = "",
    gateway: ModelGateway | None = None,
    emit: EventEmitter | None = None,
    stream: bool = False,
) -> AgentResult:
    """执行一次受控多轮 tool-loop turn。stream=True 时通过 emit 产出 TOKEN_DELTA。"""
    return _run_turn_loop(
        user_input=user_input,
        context=context,
        registry=registry,
        config=config,
        tool_context=tool_context,
        dynamic_context=dynamic_context,
        gateway=gateway,
        emit=emit,
        stream=stream,
    )


def run_turn_stream(
    *,
    user_input: str,
    context: ContextManager,
    registry: ToolRegistry,
    config: AgentConfig,
    tool_context: ToolContext,
    dynamic_context: str = "",
    gateway: ModelGateway | None = None,
) -> Iterator[AgentEvent]:
    """
    流式执行 turn，逐事件 yield。

    约定：
    - 产出 ROUND_START / TOKEN_DELTA / TOOL_* / TURN_END / ERROR。
    - TURN_END 之后生成器结束；调用方仍可通过 context.history 读取完整对话。
    """
    gateway = gateway or get_gateway()
    context.record([AgentMessage(role=Role.USER.value, content=user_input)])

    for round_index in range(1, config.max_iterations + 1):
        context.maybe_compact()

        yield AgentEvent(type=AgentEventType.ROUND_START, round_index=round_index)

        request = _build_round_request(
            context=context,
            registry=registry,
            config=config,
            tool_context=tool_context,
            dynamic_context=dynamic_context,
        )

        response_text = ""
        finish_reason = "stop"
        usage = TokenUsage()
        tool_calls: list = []

        for event in gateway.stream(request):
            if event.type == StreamEventType.DELTA and event.text:
                response_text += event.text
                yield AgentEvent(
                    type=AgentEventType.TOKEN_DELTA,
                    round_index=round_index,
                    text=event.text,
                )
            elif event.type == StreamEventType.DONE and event.response is not None:
                response_text = event.response.text or response_text
                finish_reason = event.response.finish_reason
                usage = event.response.usage
                tool_calls = list(event.response.tool_calls)

        if tool_calls:
            context.record(
                [
                    AgentMessage(
                        role=Role.ASSISTANT.value,
                        content=response_text,
                        tool_calls=tuple(tool_calls),
                    )
                ]
            )

            tool_messages: list[AgentMessage] = []
            for call in tool_calls:
                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL_BEGIN,
                    round_index=round_index,
                    tool_name=call.name,
                    tool_call_id=call.id,
                )

                result = registry.dispatch(call, tool_context)
                tool_messages.append(
                    AgentMessage(
                        role=Role.TOOL.value,
                        content=result.content,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL_END,
                    round_index=round_index,
                    tool_name=call.name,
                    tool_call_id=call.id,
                    text=result.content[:200],
                    error="tool_error" if result.is_error else None,
                )

            context.record(tool_messages)
            continue

        context.record([AgentMessage(role=Role.ASSISTANT.value, content=response_text)])
        yield AgentEvent(
            type=AgentEventType.TURN_END,
            round_index=round_index,
            text=response_text,
        )
        return

    yield AgentEvent(
        type=AgentEventType.ERROR,
        round_index=config.max_iterations,
        error="max_iterations_exceeded",
    )
    raise MaxIterationsError(
        f"达到最大迭代次数 {config.max_iterations}，turn 终止"
    )
