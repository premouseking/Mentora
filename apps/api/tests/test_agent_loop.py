"""
Agent tool-loop 契约测试。

约束：
- 全部使用 FakeProvider 与内存工具，不需要外部凭证或网络。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
"""

from __future__ import annotations

import json

import pytest

from mentora.agent_runtime.context import ContextManager
from mentora.agent_runtime.contracts import AgentConfig, AgentEventType, AgentMessage
from mentora.agent_runtime.exceptions import ContextBudgetExceeded, MaxIterationsError
from mentora.agent_runtime.loop import run_turn, run_turn_stream
from mentora.agent_runtime.session import AgentSession
from mentora.agent_runtime.tools.base import Tool, ToolContext
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.agent_runtime.contracts import ToolResult
from mentora.model_gateway.contracts import ToolCall
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.base import ProviderResponse
from mentora.model_gateway.registry import ProviderRegistry

FAKE = "mentora.model_gateway.providers.fake.FakeProvider"


class _EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "回显输入文本，供测试 tool-loop。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    def run(self, arguments: dict, context: ToolContext) -> ToolResult:
        return ToolResult(content=json.dumps({"echo": arguments.get("text", "")}))


def _gateway(script: list) -> ModelGateway:
    config = {
        "providers": {"p": {"class": FAKE, "options": {"script": script}}},
        "routing": {"balanced": [{"provider": "p", "model": "m"}]},
    }
    return ModelGateway(registry=ProviderRegistry(config=config))


def test_agent_loop_executes_tool_then_completes():
    gateway = _gateway(
        [
            ProviderResponse(
                text="",
                model="m",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(id="call_1", name="echo", arguments='{"text": "hello"}')
                ],
            ),
            ProviderResponse(text="工具已执行，最终回答。", model="m", finish_reason="stop"),
        ]
    )
    context = ContextManager()
    registry = ToolRegistry([_EchoTool()])
    config = AgentConfig(max_iterations=4)

    result = run_turn(
        user_input="请回显 hello",
        context=context,
        registry=registry,
        config=config,
        tool_context=ToolContext(),
        gateway=gateway,
    )

    assert result.text == "工具已执行，最终回答。"
    assert result.rounds == 2
    roles = [m.role for m in result.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    tool_msg = result.messages[2]
    assert tool_msg.tool_call_id == "call_1"
    assert json.loads(tool_msg.content)["echo"] == "hello"


def test_agent_loop_direct_answer_without_tools():
    gateway = _gateway(
        [ProviderResponse(text="直接回答，无需工具。", model="m", finish_reason="stop")]
    )
    result = run_turn(
        user_input="你好",
        context=ContextManager(),
        registry=ToolRegistry([_EchoTool()]),
        config=AgentConfig(),
        tool_context=ToolContext(),
        gateway=gateway,
    )

    assert result.text == "直接回答，无需工具。"
    assert result.rounds == 1
    assert len(result.messages) == 2


def test_agent_loop_sends_dynamic_context_as_contextual_user_message():
    gateway = _gateway(
        [ProviderResponse(text="ok", model="m", finish_reason="stop")]
    )
    run_turn(
        user_input="你好",
        context=ContextManager(),
        registry=ToolRegistry([_EchoTool()]),
        config=AgentConfig(prompt_version="agent-test-v1"),
        tool_context=ToolContext(
            owner_id="owner-1",
            course_id="course-1",
            scope_revision_id="scope-1",
        ),
        dynamic_context="当前单元：矩阵",
        gateway=gateway,
    )

    provider = gateway._registry.get_provider("p")
    request = provider.calls[0]
    assert request.metadata["prompt_version"] == "agent-test-v1"
    assert "agent-test-v1" in request.messages[0]["content"]
    assert "</learning_context>" not in request.messages[0]["content"]
    assert "当前单元：矩阵" not in request.messages[0]["content"]
    assert request.messages[1]["role"] == "user"
    assert "<course_scope>" in request.messages[1]["content"]
    assert "<available_tools>" in request.messages[1]["content"]
    assert "<learning_context>" in request.messages[1]["content"]
    assert request.messages[2] == {"role": "user", "content": "你好"}


def test_agent_loop_raises_on_max_iterations():
    gateway = _gateway(
        [
            ProviderResponse(
                text="",
                model="m",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(id="call_1", name="echo", arguments='{"text": "x"}')
                ],
            )
        ]
        * 3
    )
    with pytest.raises(MaxIterationsError):
        run_turn(
            user_input="无限循环",
            context=ContextManager(),
            registry=ToolRegistry([_EchoTool()]),
            config=AgentConfig(max_iterations=2),
            tool_context=ToolContext(),
            gateway=gateway,
        )


def test_agent_loop_raises_when_context_budget_exceeded():
    gateway = _gateway(
        [ProviderResponse(text="不应调用", model="m", finish_reason="stop")]
    )
    with pytest.raises(ContextBudgetExceeded):
        run_turn(
            user_input="这是一段很长的输入",
            context=ContextManager(token_budget=1),
            registry=ToolRegistry([_EchoTool()]),
            config=AgentConfig(),
            tool_context=ToolContext(),
            gateway=gateway,
        )


def test_agent_session_emits_tool_events():
    gateway = _gateway(
        [
            ProviderResponse(
                text="",
                model="m",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(id="call_1", name="echo", arguments='{"text": "ping"}')
                ],
            ),
            ProviderResponse(text="完成", model="m", finish_reason="stop"),
        ]
    )
    events: list[str] = []

    def emit(event) -> None:
        events.append(event.type.value)

    session = AgentSession(tools=[_EchoTool()], gateway=gateway)
    session.run("测试", emit=emit)

    assert events == [
        AgentEventType.ROUND_START.value,
        AgentEventType.TOOL_CALL_BEGIN.value,
        AgentEventType.TOOL_CALL_END.value,
        AgentEventType.ROUND_START.value,
        AgentEventType.TURN_END.value,
    ]


def test_tool_registry_unknown_tool_returns_error():
    registry = ToolRegistry([])
    result = registry.dispatch(
        ToolCall(id="x", name="missing", arguments="{}"),
        ToolContext(),
    )
    assert result.is_error is True
    assert "未知工具" in result.content


def test_agent_loop_stream_emits_token_deltas():
    gateway = _gateway(
        [ProviderResponse(text="流式回答", model="m", finish_reason="stop")]
    )
    events = list(
        run_turn_stream(
            user_input="你好",
            context=ContextManager(),
            registry=ToolRegistry([_EchoTool()]),
            config=AgentConfig(),
            tool_context=ToolContext(),
            gateway=gateway,
        )
    )

    deltas = [e for e in events if e.type == AgentEventType.TOKEN_DELTA]
    assert "".join(e.text for e in deltas) == "流式回答"
    assert events[-1].type == AgentEventType.TURN_END
    assert events[-1].text == "流式回答"


def test_agent_loop_stream_yields_before_turn_end():
    gateway = _gateway(
        [ProviderResponse(text="流式回答", model="m", finish_reason="stop")]
    )
    stream = run_turn_stream(
        user_input="你好",
        context=ContextManager(),
        registry=ToolRegistry([_EchoTool()]),
        config=AgentConfig(),
        tool_context=ToolContext(),
        gateway=gateway,
    )

    first = next(stream)
    second = next(stream)

    assert first.type == AgentEventType.ROUND_START
    assert second.type == AgentEventType.TOKEN_DELTA
    assert second.text == "流"


def test_agent_loop_stream_tool_then_answer():
    gateway = _gateway(
        [
            ProviderResponse(
                text="",
                model="m",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(id="call_1", name="echo", arguments='{"text": "hi"}')
                ],
            ),
            ProviderResponse(text="完成", model="m", finish_reason="stop"),
        ]
    )
    events = list(
        run_turn_stream(
            user_input="测试",
            context=ContextManager(),
            registry=ToolRegistry([_EchoTool()]),
            config=AgentConfig(),
            tool_context=ToolContext(),
            gateway=gateway,
        )
    )

    event_types = [e.type for e in events]
    assert AgentEventType.TOOL_CALL_BEGIN in event_types
    assert AgentEventType.TOKEN_DELTA in event_types
    assert events[-1].type == AgentEventType.TURN_END
    assert events[-1].text == "完成"
