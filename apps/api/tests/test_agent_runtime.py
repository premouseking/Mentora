"""
Agent Runtime 端到端集成测试。

使用 FakeProvider 驱动完整的 Agent 工具调用循环，
覆盖多轮工具调用、无工具、工具失败和上下文预算场景。

@module tests/test_agent_runtime
"""

import os

import pytest

# 确保 DJANGO_SETTINGS_MODULE 在 import 前设置
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import asyncio
from unittest.mock import MagicMock

import django
django.setup()

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.agents.tutor import TutorAgent
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.events import EventEmitter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.context import AgentContext
from mentora.agent_runtime.schemas.output import AgentOutput
from mentora.agent_runtime.schemas.task import BudgetConfig, OrchestratorTask
from mentora.agent_runtime.tools.base import Tool, ToolDefinition, ToolResult
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.fake import FakeProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import FunctionCall, Message, ToolCall
from mentora.model_gateway.structured_output import StructuredOutputValidator


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture
def token_counter():
    return TokenCounter()


@pytest.fixture
def prompt_manager():
    """使用内置 tutor.json 模板的 PromptManager。"""
    return PromptManager()


@pytest.fixture
def budget_config():
    return BudgetConfig(max_tokens=8000, system_reserved=1500, output_reserved=1500)


@pytest.fixture
def context_manager(budget_config, token_counter):
    return ContextManager(budget=budget_config, counter=token_counter)


@pytest.fixture
def emitter():
    events = []
    return EventEmitter(callback=lambda e, p: events.append((e, p))), events


@pytest.fixture
def tool_registry():
    """注册一个简单的 mock 工具。"""
    class MockRetrieveTool(Tool):
        async def execute(self, args, ctx):
            query = args.get("query", "")
            return ToolResult(
                tool_name="retrieve_evidence",
                success=True,
                result={"query": query, "results": [{"content": "Mock evidence for: " + query, "page": 1}]},
            )

    class FailingTool(Tool):
        async def execute(self, args, ctx):
            return ToolResult(
                tool_name="failing_tool",
                success=False,
                error="Simulated tool failure",
            )

    registry = ToolRegistry()
    registry.register(
        MockRetrieveTool(),
        ToolDefinition(
            name="retrieve_evidence",
            description="Search learning materials for relevant content",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Result count", "default": 5},
                },
                "required": ["query"],
            },
            agent_roles={"tutor", "planner"},
        ),
    )
    registry.register(
        FailingTool(),
        ToolDefinition(
            name="failing_tool",
            description="A tool that always fails",
            parameters={"type": "object", "properties": {}},
            agent_roles={"tester"},
        ),
    )
    return registry


# ── Helper ────────────────────────────────────────────

def _build_tool_call(id: str, name: str, args: str) -> ToolCall:
    return ToolCall(id=id, function=FunctionCall(name=name, arguments=args))


def _build_orchestrator(
    fake_provider: FakeProvider,
    prompt_manager: PromptManager,
    context_manager: ContextManager,
    tool_registry: ToolRegistry,
    emitter_events: tuple,
) -> Orchestrator:
    """构建完整的 Orchestrator 实例。"""
    emitter, _ = emitter_events
    router = TaskRouter(default_provider=fake_provider)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    return Orchestrator(
        agent_map={"tutor": tutor},
        prompt_manager=prompt_manager,
        context_manager=context_manager,
        emitter=emitter,
    )


# ── Test: 无工具调用（纯文本回复） ─────────────────

@pytest.mark.django_db
def test_tutor_no_tool_calls(prompt_manager, context_manager, tool_registry, emitter):
    """TutorAgent 在无需工具时直接返回文本回复。"""
    fake = FakeProvider(
        text_responses=["这是关于光合作用的简要回答。"],
    )

    orch = _build_orchestrator(fake, prompt_manager, context_manager, tool_registry, emitter)

    task = OrchestratorTask(
        id="test-no-tools",
        agent_role="tutor",
        user_message="什么是光合作用？",
    )

    result = asyncio.run(orch.run(task))
    _, events_list = emitter

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.final_message == "这是关于光合作用的简要回答。"
    assert result.final_output.finish_reason == "completed"
    assert len(result.final_output.tool_calls_made) == 0

    # 验证事件序列
    event_names = [e[0] for e in events_list]
    assert "agent.run.started" in event_names
    assert "agent.run.completed" in event_names


# ── Test: 单次工具调用 ────────────────────────────

@pytest.mark.django_db
def test_tutor_single_tool_call(prompt_manager, context_manager, tool_registry, emitter):
    """TutorAgent 先调用 retrieve_evidence 获取资料，再给出最终回答。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [
                _build_tool_call("call_1", "retrieve_evidence", '{"query": "光合作用 原理"}'),
            ],
        ],
        text_responses=["根据资料显示，光合作用是植物利用光能转化二氧化碳和水为有机物和氧气的过程。"],
    )

    orch = _build_orchestrator(fake, prompt_manager, context_manager, tool_registry, emitter)

    task = OrchestratorTask(
        id="test-single-tool",
        agent_role="tutor",
        user_message="光合作用的原理是什么？",
    )

    result = asyncio.run(orch.run(task))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.finish_reason == "completed"
    assert "光合作用" in result.final_output.final_message
    assert len(result.final_output.tool_calls_made) == 1
    assert result.final_output.tool_calls_made[0].tool_name == "retrieve_evidence"
    assert result.final_output.tool_calls_made[0].success is True
    assert result.total_tool_calls == 1


# ── Test: 多轮工具调用 ────────────────────────────

@pytest.mark.django_db
def test_tutor_multi_tool_calls(prompt_manager, context_manager, tool_registry, emitter):
    """TutorAgent 执行多轮工具调用后聚合信息给出回答。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [
                _build_tool_call("call_1", "retrieve_evidence", '{"query": "细胞呼吸 过程"}'),
            ],
            [
                _build_tool_call("call_2", "retrieve_evidence", '{"query": "细胞呼吸 能量转换"}'),
            ],
        ],
        text_responses=["细胞呼吸分为有氧呼吸和无氧呼吸，主要发生在线粒体中，将葡萄糖分解为ATP。"],
    )

    orch = _build_orchestrator(fake, prompt_manager, context_manager, tool_registry, emitter)

    task = OrchestratorTask(
        id="test-multi-tool",
        agent_role="tutor",
        user_message="细胞呼吸的过程是什么？",
        max_tool_rounds=5,
    )

    result = asyncio.run(orch.run(task))

    assert result.status == "completed"
    assert result.final_output is not None
    assert len(result.final_output.tool_calls_made) == 2
    assert result.total_tool_calls == 2


# ── Test: 工具调用达到上限 ──────────────────────

@pytest.mark.django_db
def test_tutor_max_rounds_reached(prompt_manager, context_manager, tool_registry, emitter):
    """当工具调用达到 max_tool_rounds 上限时，返回 max_rounds 状态。"""
    # 构造 3 轮工具调用，但只给 2 轮上限
    fake = FakeProvider(
        tool_call_scenarios=[
            [_build_tool_call("call_1", "retrieve_evidence", '{"query": "x"}')],
            [_build_tool_call("call_2", "retrieve_evidence", '{"query": "y"}')],
            [_build_tool_call("call_3", "retrieve_evidence", '{"query": "z"}')],
        ],
    )

    orch = _build_orchestrator(fake, prompt_manager, context_manager, tool_registry, emitter)

    task = OrchestratorTask(
        id="test-max-rounds",
        agent_role="tutor",
        user_message="请解释三件事。",
        max_tool_rounds=2,
    )

    result = asyncio.run(orch.run(task))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.finish_reason == "max_rounds"
    assert len(result.final_output.tool_calls_made) == 2
    assert result.total_tool_calls == 2


# ── Test: 编排器错误处理 ──────────────────────────

@pytest.mark.django_db
def test_orchestrator_invalid_agent(prompt_manager, context_manager, tool_registry, emitter):
    """请求不存在的 Agent 角色时返回错误。"""
    fake = FakeProvider()
    orch = _build_orchestrator(fake, prompt_manager, context_manager, tool_registry, emitter)

    task = OrchestratorTask(
        id="test-invalid-agent",
        agent_role="nonexistent_agent",
        user_message="测试",
    )

    result = asyncio.run(orch.run(task))

    assert result.status == "failed"
    assert "nonexistent_agent" in result.error_message
    assert result.error_code == "orchestrator_error"


# ── Test: 上下文预算裁剪 ──────────────────────────

@pytest.mark.django_db
def test_context_budget_truncation(token_counter, budget_config):
    """上下文超过预算时，按优先级裁剪历史消息和证据。"""
    from mentora.agent_runtime.context.manager import ContextManager

    tight_budget = BudgetConfig(max_tokens=500, system_reserved=200, output_reserved=100)
    cm = ContextManager(budget=tight_budget, counter=token_counter)

    # 构建大量历史消息（会被裁剪）
    history = [
        Message(role="user", content="长消息 " * 100),
        Message(role="assistant", content="长回复 " * 100),
        Message(role="user", content="超长消息 " * 200),
    ]

    messages, alloc = cm.build_messages(
        system_prompt="你是学习助教。",
        user_message="简短问题",
        history=history,
    )

    # 验证预算内
    assert alloc.total_tokens <= tight_budget.available_for_messages
    # 验证有系统提示词
    assert any(m.role == "system" for m in messages)
    # 验证有用户消息
    assert messages[-1].role == "user"
    # 历史可能被裁剪（至少不全是全量）
    assert len(messages) < 5  # system + 3 history + user = 5 如果全保留


# ── Test: TokenCounter ──────────────────────────

def test_token_counter_basic(token_counter):
    """Token 计数器基本功能。"""
    assert token_counter.count("hello") >= 1
    assert token_counter.count("") == 0
    assert token_counter.count("a" * 300) >= 100

    msgs = [
        Message(role="user", content="问题一"),
        Message(role="assistant", content="回答一"),
    ]
    assert token_counter.count_messages(msgs) >= 2


# ── Test: PromptManager ─────────────────────────

def test_prompt_manager_render(prompt_manager):
    """PromptManager 渲染模板变量。"""
    result = prompt_manager.render("tutor", {
        "course_name": "生物学",
        "source_titles": "课本第一章",
    })
    assert "生物学" in result
    assert "课本第一章" in result
    assert "Mentora 学习助教" in result
    assert "{{" not in result


def test_prompt_manager_missing_template(prompt_manager):
    """请求不存在的模板时抛出 KeyError。"""
    with pytest.raises(KeyError):
        prompt_manager.get("nonexistent")


# ── Test: ToolRegistry ──────────────────────────

def test_tool_registry_role_filter(tool_registry):
    """ToolRegistry 按角色过滤工具。"""
    tutor_tools = tool_registry.get_for_agent("tutor")
    assert len(tutor_tools) == 1
    assert tutor_tools[0].name == "retrieve_evidence"

    planner_tools = tool_registry.get_for_agent("planner")
    assert len(planner_tools) == 1

    other_tools = tool_registry.get_for_agent("other")
    assert len(other_tools) == 0


def test_tool_registry_openai_format(tool_registry):
    """工具定义转为 OpenAI tools 格式。"""
    tools = tool_registry.get_openai_tools("tutor")
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "retrieve_evidence"


# ── Test: EventEmitter ─────────────────────────

def test_event_emitter():
    """EventEmitter 发射事件到回调。"""
    events = []
    em = EventEmitter(callback=lambda e, p: events.append((e, p)))

    em.agent_run_started("t1", "tutor")
    em.tool_call("t1", "retrieve_evidence", {"query": "test"})
    em.tool_result("t1", "retrieve_evidence", True, "preview text")
    em.agent_run_completed("t1", "tutor", {"result": "ok"})

    event_names = [e[0] for e in events]
    assert event_names == [
        "agent.run.started",
        "agent.tool.call",
        "agent.tool.result",
        "agent.run.completed",
    ]


# ── Test: FakeProvider ─────────────────────────

@pytest.mark.asyncio
async def test_fake_provider_text_response():
    """FakeProvider 返回预置文本。"""
    fake = FakeProvider(text_responses=["第一轮", "第二轮"])
    resp1 = await fake.chat(messages=[])
    assert resp1.content == "第一轮"

    resp2 = await fake.chat(messages=[])
    assert resp2.content == "第二轮"


@pytest.mark.asyncio
async def test_fake_provider_tool_calls():
    """FakeProvider 返回预置工具调用。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [_build_tool_call("c1", "search", '{"q":"test"}')],
        ],
        text_responses=["总结"],
    )
    resp1 = await fake.chat(messages=[])
    assert resp1.tool_calls is not None
    assert resp1.tool_calls[0].function.name == "search"

    resp2 = await fake.chat(messages=[])
    assert resp2.content == "总结"


@pytest.mark.asyncio
async def test_fake_provider_error_injection():
    """FakeProvider 在指定轮次注入错误。"""
    fake = FakeProvider(
        text_responses=["fine"],
        inject_error_at_round=1,
    )
    with pytest.raises(RuntimeError, match="injected error"):
        await fake.chat(messages=[])


# ── Test: OrchestratorTask Schema ──────────────

def test_orchestrator_task_defaults():
    """OrchestratorTask 默认值正确。"""
    task = OrchestratorTask(
        id="t1",
        agent_role="tutor",
        user_message="测试问题",
    )
    assert task.mode == "single"
    assert task.max_tool_rounds == 5
    assert task.budget_config.max_tokens == 8000
    assert task.pipeline_steps is None


def test_orchestrator_task_serialization():
    """OrchestratorTask JSON 序列化/反序列化。"""
    task = OrchestratorTask(
        id="t1",
        agent_role="tutor",
        user_message="问题",
        context_sources=["sv-1", "sv-2"],
        max_tool_rounds=3,
    )
    json_str = task.model_dump_json()
    restored = OrchestratorTask.model_validate_json(json_str)
    assert restored.id == "t1"
    assert restored.agent_role == "tutor"
    assert restored.max_tool_rounds == 3
    assert restored.context_sources == ["sv-1", "sv-2"]


# ════════════════════════════════════════════════════════════
# Phase 2 Tests
# ════════════════════════════════════════════════════════════


# ── Test: FakeProvider 流式 ──────────────────────────

@pytest.mark.asyncio
async def test_fake_provider_chat_stream_text():
    """FakeProvider.chat_stream() 逐 chunk 输出文本。"""
    fake = FakeProvider(text_responses=["Hello World!"])
    chunks = []
    async for chunk in fake.chat_stream(messages=[]):
        chunks.append(chunk)

    # 应至少有内容 chunk + 最终 chunk
    assert len(chunks) >= 2
    # 内容 chunk 含文本
    content_chunks = [c for c in chunks if c.content]
    assert len(content_chunks) > 0
    # 最终 chunk 有 finish_reason="stop"
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_fake_provider_chat_stream_tool_call():
    """FakeProvider.chat_stream() 流式返回工具调用。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [_build_tool_call("call_1", "search", '{"q":"test"}')],
        ],
    )
    chunks = []
    async for chunk in fake.chat_stream(messages=[]):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].tool_calls is not None
    assert chunks[0].tool_calls[0].function.name == "search"


# ── Test: TutorAgent 流式 ─────────────────────────────

@pytest.mark.django_db
def test_tutor_run_stream_text_response(prompt_manager, context_manager, tool_registry, emitter):
    """TutorAgent.run_stream() 流式返回纯文本。"""
    fake = FakeProvider(text_responses=["流式文本回复测试。"])
    _, events_list = emitter
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    # 构建 AgentInput
    system_prompt = prompt_manager.render("tutor", {
        "course_name": "测试课程",
        "source_titles": "测试资料",
    })
    messages = [Message(role="system", content=system_prompt), Message(role="user", content="测试问题")]
    ctx = AgentContext(messages=messages, system_prompt=system_prompt)
    agent_input = AgentInput(task_id="stream-test", user_message="测试问题", context=ctx)

    output = asyncio.run(tutor.run_stream(agent_input, emitter=emitter[0]))

    assert output.final_message == "流式文本回复测试。"
    assert output.finish_reason == "completed"
    assert len(output.tool_calls_made) == 0


@pytest.mark.django_db
def test_tutor_run_stream_with_tool_call(prompt_manager, context_manager, tool_registry, emitter):
    """TutorAgent.run_stream() 流式 + 工具调用循环。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [_build_tool_call("call_1", "retrieve_evidence", '{"query": "光合作用"}')],
        ],
        text_responses=["根据资料，光合作用是..."],
    )
    em, _ = emitter
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    system_prompt = prompt_manager.render("tutor", {
        "course_name": "测试",
        "source_titles": "测试",
    })
    messages = [Message(role="system", content=system_prompt), Message(role="user", content="测试")]
    ctx = AgentContext(messages=messages, system_prompt=system_prompt)
    agent_input = AgentInput(task_id="stream-tool", user_message="测试", context=ctx)

    output = asyncio.run(tutor.run_stream(agent_input, emitter=em))

    assert output.final_message == "根据资料，光合作用是..."
    assert output.finish_reason == "completed"
    assert len(output.tool_calls_made) == 1
    assert output.tool_calls_made[0].tool_name == "retrieve_evidence"


# ── Test: PlannerAgent ────────────────────────────────

@pytest.mark.django_db
def test_planner_agent_no_tools(prompt_manager, context_manager, tool_registry, emitter):
    """PlannerAgent 直接返回学习计划（无工具调用）。"""
    fake = FakeProvider(text_responses=["## 学习计划\n\n### 阶段 1：细胞生物学基础\n- 学习内容：细胞结构...\n- 预期时间：2 小时"])
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    from mentora.agent_runtime.agents.planner import PlannerAgent
    planner = PlannerAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    system_prompt = prompt_manager.render("planner", {
        "course_name": "生物学",
        "source_titles": "课本第一至三章",
    })
    messages = [Message(role="system", content=system_prompt), Message(role="user", content="帮我制定生物学学习计划")]
    ctx = AgentContext(messages=messages, system_prompt=system_prompt)
    agent_input = AgentInput(task_id="plan-1", user_message="帮我制定生物学学习计划", context=ctx)

    output = asyncio.run(planner.run(agent_input))

    assert output.agent_role == "planner"
    assert "学习计划" in output.final_message
    assert output.finish_reason == "completed"


@pytest.mark.django_db
def test_planner_agent_with_tool_call(prompt_manager, context_manager, tool_registry, emitter):
    """PlannerAgent 使用 retrieve_evidence 工具检索资料后生成计划。"""
    fake = FakeProvider(
        tool_call_scenarios=[
            [_build_tool_call("call_1", "retrieve_evidence", '{"query": "细胞生物学 学习计划"}')],
        ],
        text_responses=["## 学习计划\n### 阶段 1：细胞生物学（2小时）\n参考：课本第一章第1-30页"],
    )
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    from mentora.agent_runtime.agents.planner import PlannerAgent
    planner = PlannerAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    system_prompt = prompt_manager.render("planner", {
        "course_name": "生物学",
        "source_titles": "课本",
    })
    messages = [Message(role="system", content=system_prompt), Message(role="user", content="制定计划")]
    ctx = AgentContext(messages=messages, system_prompt=system_prompt)
    agent_input = AgentInput(task_id="plan-2", user_message="制定计划", context=ctx)

    output = asyncio.run(planner.run(agent_input))

    assert output.agent_role == "planner"
    assert len(output.tool_calls_made) == 1
    assert output.tool_calls_made[0].tool_name == "retrieve_evidence"


# ── Test: ClarifierAgent ──────────────────────────────

@pytest.mark.django_db
def test_clarifier_agent(prompt_manager, context_manager, emitter):
    """ClarifierAgent 对模糊意图给出澄清问题。"""
    fake = FakeProvider(text_responses=["我理解你想学习生物学。请告诉我：\n1. 你的学习目标是什么？（考试/兴趣/补充知识）\n2. 你目前的生物学基础如何？"])
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())
    tool_registry = ToolRegistry()

    from mentora.agent_runtime.agents.clarifier import ClarifierAgent
    clarifier = ClarifierAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    system_prompt = prompt_manager.render("clarifier", {
        "course_name": "生物学",
        "source_titles": "课本",
    })
    messages = [Message(role="system", content=system_prompt), Message(role="user", content="我想学生物")]
    ctx = AgentContext(messages=messages, system_prompt=system_prompt)
    agent_input = AgentInput(task_id="clarify-1", user_message="我想学生物", context=ctx)

    output = asyncio.run(clarifier.run(agent_input))

    assert output.agent_role == "clarifier"
    assert output.final_message
    assert output.finish_reason == "completed"
    assert len(output.tool_calls_made) == 0  # Clarifier 不使用工具


# ── Test: EventEmitter 流式事件 ───────────────────────

def test_event_emitter_response_stream():
    """EventEmitter.agent_response_stream 事件。"""
    events = []
    em = EventEmitter(callback=lambda e, p: events.append((e, p)))

    em.agent_response_stream("t1", "第一", is_final=False)
    em.agent_response_stream("t1", "个", is_final=False)
    em.agent_response_stream("t1", "回", is_final=False)
    em.agent_response_stream("t1", "答", is_final=False)
    em.agent_response_stream("t1", "", is_final=True)

    assert len(events) == 5
    assert events[-1][1]["is_final"] is True
    assert events[0][0] == "agent.response_stream"


def test_event_emitter_pipeline_steps():
    """EventEmitter step_started/step_completed 事件。"""
    events = []
    em = EventEmitter(callback=lambda e, p: events.append((e, p)))

    em.step_started("t1", 0, "clarifier")
    em.step_completed("t1", 0, "First step output")
    em.step_started("t1", 1, "planner")
    em.step_completed("t1", 1, "Second step output")

    event_names = [e[0] for e in events]
    assert event_names == [
        "agent.step.started",
        "agent.step.completed",
        "agent.step.started",
        "agent.step.completed",
    ]


# ── Test: Pipeline 模式端到端 ─────────────────────────

@pytest.mark.django_db
def test_pipeline_clarifier_to_planner_to_tutor(prompt_manager, context_manager, tool_registry, emitter):
    """Pipeline 端到端：Clarifier → Planner → Tutor。"""
    from mentora.agent_runtime.agents.clarifier import ClarifierAgent
    from mentora.agent_runtime.agents.planner import PlannerAgent

    fake = FakeProvider(
        text_responses=[
            # Clarifier 输出
            "你想学习什么阶段的生物学？请说明目标。",
            # Planner 输出
            "## 学习计划\n### 阶段1：基础概念（1h）\n### 阶段2：深入理解（2h）",
            # Tutor 输出
            "细胞是生物体结构和功能的基本单位。",
        ],
    )
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())
    em, events_list = emitter

    clarifier = ClarifierAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )
    planner = PlannerAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )
    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    orch = Orchestrator(
        agent_map={
            "clarifier": clarifier,
            "planner": planner,
            "tutor": tutor,
        },
        prompt_manager=prompt_manager,
        context_manager=context_manager,
        emitter=em,
    )

    from mentora.agent_runtime.schemas.task import PipelineStep
    task = OrchestratorTask(
        id="pipeline-e2e",
        mode="pipeline",
        agent_role="clarifier",
        user_message="我想学生物学",
        pipeline_steps=[
            PipelineStep(
                agent_role="clarifier",
                task_instruction="澄清用户意图",
                output_key="clarified_intent",
            ),
            PipelineStep(
                agent_role="planner",
                task_instruction="基于澄清结果制定学习计划",
                input_from="clarified_intent",
                output_key="plan",
            ),
            PipelineStep(
                agent_role="tutor",
                task_instruction="根据计划回答用户的第一个学习问题",
                input_from="plan",
                output_key="answer",
            ),
        ],
    )

    result = asyncio.run(orch.run(task))

    assert result.status == "completed"
    assert len(result.agent_outputs) == 3
    assert result.agent_outputs[0].agent_role == "clarifier"
    assert result.agent_outputs[1].agent_role == "planner"
    assert result.agent_outputs[2].agent_role == "tutor"

    # 验证事件
    event_names = [e[0] for e in events_list]
    assert "agent.step.started" in event_names
    assert "agent.step.completed" in event_names
    assert event_names.count("agent.step.started") == 3


@pytest.mark.django_db
def test_pipeline_step_error_handling(prompt_manager, context_manager, tool_registry, emitter):
    """Pipeline 中某步失败时，后续步骤不执行。"""
    from mentora.agent_runtime.agents.clarifier import ClarifierAgent

    # Clarifier 正常，Planner 不存在导致 KeyError
    fake = FakeProvider(text_responses=["澄清问题: 你的目标是什么？"])
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())
    em, events_list = emitter

    clarifier = ClarifierAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    orch = Orchestrator(
        agent_map={"clarifier": clarifier},
        prompt_manager=prompt_manager,
        context_manager=context_manager,
        emitter=em,
    )

    from mentora.agent_runtime.schemas.task import PipelineStep
    task = OrchestratorTask(
        id="pipeline-error",
        mode="pipeline",
        agent_role="clarifier",
        user_message="测试",
        pipeline_steps=[
            PipelineStep(agent_role="clarifier", task_instruction="澄清", output_key="out1"),
            PipelineStep(agent_role="nonexistent", task_instruction="会失败", output_key="out2"),
            PipelineStep(agent_role="clarifier", task_instruction="不应执行", output_key="out3"),
        ],
    )

    result = asyncio.run(orch.run(task))

    # Pipeline 失败但返回 partial 结果
    assert result.status == "failed"
    assert len(result.agent_outputs) == 2  # 仅执行了第 1 步，第 2 步失败，第 3 步未执行
    assert result.agent_outputs[0].agent_role == "clarifier"
    assert result.agent_outputs[1].finish_reason == "error"


# ── Test: PromptManager 新模板 ────────────────────────

def test_prompt_manager_planner_template(prompt_manager):
    """Planner 模板加载和渲染。"""
    result = prompt_manager.render("planner", {
        "course_name": "生物学",
        "source_titles": "课本",
    })
    assert "学习规划师" in result
    assert "生物学" in result
    assert "{{" not in result


def test_prompt_manager_clarifier_template(prompt_manager):
    """Clarifier 模板加载和渲染。"""
    result = prompt_manager.render("clarifier", {
        "course_name": "数学",
        "source_titles": "教材",
    })
    assert "澄清" in result
    assert "数学" in result
    assert "{{" not in result


# ── Test: ModelGateway chat_stream ───────────────────

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_gateway_chat_stream():
    """ModelGateway.chat_stream() 流式调用。"""
    fake = FakeProvider(text_responses=["流式网关测试"])
    router = TaskRouter(default_provider=fake)
    gateway = ModelGateway(router=router, audit_enabled=False)

    messages = [Message(role="user", content="测试")]
    chunks = []
    async for chunk in gateway.chat_stream(
        task_type="tutor",
        messages=messages,
    ):
        chunks.append(chunk)

    assert len(chunks) >= 1
    content = "".join(c.content or "" for c in chunks)
    assert "流式网关测试" in content
