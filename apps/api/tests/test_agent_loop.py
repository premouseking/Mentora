"""
turn_loop 契约测试。

约束：
- 全部使用 FakeProvider 与内存工具，不需要外部凭证或网络。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.agents.turn_loop import run_tool_loop
from mentora.agent_runtime.schemas.context import AgentContext
from mentora.agent_runtime.tools.base import Tool, ToolDefinition, ToolResult
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.fake import FakeProvider, make_tool_call
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import Message
from mentora.model_gateway.structured_output import StructuredOutputValidator


class _EchoTool(Tool):
    async def execute(self, args, ctx):
        return ToolResult(
            tool_name="echo",
            success=True,
            result={"echo": args.get("text", "")},
        )


def _registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        _EchoTool(),
        ToolDefinition(
            name="echo",
            description="回显输入",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            agent_roles={"tester"},
        ),
    )
    return registry


def _agent_input(messages: list[Message]) -> AgentInput:
    ctx = AgentContext(messages=messages, system_prompt="test")
    return AgentInput(
        task_id="t1",
        user_message="hello",
        context=ctx,
        max_tool_rounds=4,
    )


@pytest.mark.django_db
def test_turn_loop_executes_tool_then_completes():
    fake = FakeProvider(
        tool_call_scenarios=[
            [make_tool_call("call_1", "echo", '{"text": "hello"}')],
        ],
        text_responses=["工具已执行，最终回答。"],
    )
    gateway = ModelGateway(
        router=TaskRouter(default_provider=fake),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
    )
    messages = [
        Message(role="system", content="你是助手"),
        Message(role="user", content="请回显 hello"),
    ]
    output = asyncio.run(
        run_tool_loop(
            agent_role="tester",
            agent_input=_agent_input(messages),
            registry=_registry_with_echo(),
            gateway=gateway,
        )
    )

    assert output.final_message == "工具已执行，最终回答。"
    assert output.finish_reason == "completed"
    assert len(output.tool_calls_made) == 1
    assert output.tool_calls_made[0].success is True


@pytest.mark.django_db
def test_turn_loop_tool_result_backfill_contains_echo_payload():
    """工具结果应 JSON 序列化真实 result，而非 arguments。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [make_tool_call("call_1", "echo", '{"text": "ping"}')],
        ],
        text_responses=["完成"],
    )
    gateway = ModelGateway(
        router=TaskRouter(default_provider=fake),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
    )

    captured_messages: list[list[Message]] = []

    class _CapturingFake(FakeProvider):
        async def chat(self, messages, tools=None, model=None):
            captured_messages.append(list(messages))
            return await super().chat(messages, tools, model)

    gateway._router._default = _CapturingFake(  # noqa: SLF001
        tool_call_scenarios=fake._tool_scenarios,
        text_responses=fake._texts,
    )

    messages = [
        Message(role="system", content="test"),
        Message(role="user", content="回显 ping"),
    ]
    asyncio.run(
        run_tool_loop(
            agent_role="tester",
            agent_input=_agent_input(messages),
            registry=_registry_with_echo(),
            gateway=gateway,
        )
    )

    # 第二次模型调用应包含 tool message，且 content 含 echo 结果
    assert len(captured_messages) >= 2
    tool_msgs = [m for m in captured_messages[1] if m.role == "tool"]
    assert len(tool_msgs) == 1
    payload = json.loads(tool_msgs[0].content or "{}")
    assert payload["success"] is True
    assert payload["result"]["echo"] == "ping"


@pytest.mark.django_db
def test_turn_loop_direct_answer_without_tools():
    fake = FakeProvider(text_responses=["直接回答，无需工具。"])
    gateway = ModelGateway(
        router=TaskRouter(default_provider=fake),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
    )
    messages = [
        Message(role="system", content="test"),
        Message(role="user", content="你好"),
    ]
    output = asyncio.run(
        run_tool_loop(
            agent_role="tester",
            agent_input=_agent_input(messages),
            registry=_registry_with_echo(),
            gateway=gateway,
        )
    )
    assert output.final_message == "直接回答，无需工具。"
    assert output.tool_calls_made == []


@pytest.mark.django_db
def test_turn_loop_max_rounds():
    fake = FakeProvider(
        tool_call_scenarios=[
            [make_tool_call("c1", "echo", '{"text": "a"}')],
            [make_tool_call("c2", "echo", '{"text": "b"}')],
            [make_tool_call("c3", "echo", '{"text": "c"}')],
        ],
    )
    gateway = ModelGateway(
        router=TaskRouter(default_provider=fake),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
    )
    agent_input = AgentInput(
        task_id="t1",
        user_message="loop",
        context=AgentContext(
            messages=[Message(role="user", content="loop")],
            system_prompt="",
        ),
        max_tool_rounds=2,
    )
    output = asyncio.run(
        run_tool_loop(
            agent_role="tester",
            agent_input=agent_input,
            registry=_registry_with_echo(),
            gateway=gateway,
        )
    )
    assert output.finish_reason == "max_rounds"
    assert len(output.tool_calls_made) == 2
