"""Agent Runtime 集成测试（独立运行，不依赖 conftest）。"""
import os
import sys
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from mentora.agent_runtime.agents.tutor import TutorAgent
from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.events import EventEmitter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.task import BudgetConfig, OrchestratorTask
from mentora.agent_runtime.tools.base import Tool, ToolDefinition, ToolResult
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.fake import FakeProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import FunctionCall, ToolCall
from mentora.model_gateway.structured_output import StructuredOutputValidator

passed = 0
failed = 0


def _tc(id, name, args):
    return ToolCall(id=id, function=FunctionCall(name=name, arguments=args))


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}: {msg}")


# Setup shared fixtures
prompt_mgr = PromptManager()
token_counter = TokenCounter()
ctx_mgr = ContextManager(BudgetConfig(), token_counter)


class MockRetrieveTool(Tool):
    async def execute(self, args, ctx):
        return ToolResult(
            tool_name="retrieve_evidence",
            success=True,
            result={"query": args.get("query", ""), "results": []},
        )


registry = ToolRegistry()
registry.register(
    MockRetrieveTool(),
    ToolDefinition(
        name="retrieve_evidence",
        description="Search learning materials",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        agent_roles={"tutor"},
    ),
)


def build_orch(fake_provider, events_list=None):
    if events_list is None:
        events_list = []
    emitter = EventEmitter(callback=lambda e, p: events_list.append((e, p)))
    router = TaskRouter(default_provider=fake_provider)
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator(), audit_enabled=False)
    tutor = TutorAgent(
        prompt_manager=prompt_mgr,
        tool_registry=registry,
        model_gateway=gateway,
    )
    orch = Orchestrator(
        agent_map={"tutor": tutor},
        prompt_manager=prompt_mgr,
        context_manager=ctx_mgr,
        emitter=emitter,
    )
    return orch, events_list


# Test 1: No tool calls
print("\nTest 1: No tool calls")
fake1 = FakeProvider(text_responses=["Photosynthesis converts light energy to chemical energy."])
orch1, events1 = build_orch(fake1)
task1 = OrchestratorTask(id="t1", agent_role="tutor", user_message="What is photosynthesis?")
result1 = asyncio.run(orch1.run(task1))
check("status completed", result1.status == "completed", result1.status)
check("has final output", result1.final_output is not None)
check("contains answer", "Photosynthesis" in result1.final_output.final_message)
check("no tool calls", len(result1.final_output.tool_calls_made) == 0)
check("events emitted", len(events1) >= 2)

# Test 2: Single tool call
print("\nTest 2: Single tool call")
fake2 = FakeProvider(
    tool_call_scenarios=[
        [_tc("c1", "retrieve_evidence", '{"query": "photosynthesis"}')],
    ],
    text_responses=["Based on materials, photosynthesis occurs in chloroplasts."],
)
orch2, events2 = build_orch(fake2)
task2 = OrchestratorTask(id="t2", agent_role="tutor", user_message="Where does photosynthesis occur?")
result2 = asyncio.run(orch2.run(task2))
check("status completed", result2.status == "completed")
check("has final output", result2.final_output is not None)
check("contains chloroplasts", "chloroplasts" in result2.final_output.final_message.lower())
check("one tool call", len(result2.final_output.tool_calls_made) == 1)
check("tool name correct", result2.final_output.tool_calls_made[0].tool_name == "retrieve_evidence")
check("tool success", result2.final_output.tool_calls_made[0].success is True)

# Test 3: Multi tool calls
print("\nTest 3: Multi tool calls")
fake3 = FakeProvider(
    tool_call_scenarios=[
        [_tc("c1", "retrieve_evidence", '{"query": "topic a"}')],
        [_tc("c2", "retrieve_evidence", '{"query": "topic b"}')],
    ],
    text_responses=["Combined answer covering both topics."],
)
orch3, events3 = build_orch(fake3)
task3 = OrchestratorTask(id="t3", agent_role="tutor", user_message="Complex question", max_tool_rounds=5)
result3 = asyncio.run(orch3.run(task3))
check("status completed", result3.status == "completed")
check("two tool calls", len(result3.final_output.tool_calls_made) == 2)
check("total tool calls", result3.total_tool_calls == 2)

# Test 4: Max rounds reached
print("\nTest 4: Max rounds reached")
fake4 = FakeProvider(
    tool_call_scenarios=[
        [_tc("c1", "retrieve_evidence", '{"query": "1"}')],
        [_tc("c2", "retrieve_evidence", '{"query": "2"}')],
        [_tc("c3", "retrieve_evidence", '{"query": "3"}')],
    ],
)
orch4, events4 = build_orch(fake4)
task4 = OrchestratorTask(id="t4", agent_role="tutor", user_message="Loop test", max_tool_rounds=2)
result4 = asyncio.run(orch4.run(task4))
check("status completed", result4.status == "completed")
check("finish reason max_rounds", result4.final_output.finish_reason == "max_rounds", result4.final_output.finish_reason)
check("exactly 2 calls", len(result4.final_output.tool_calls_made) == 2)

# Test 5: Invalid agent role
print("\nTest 5: Invalid agent role")
fake5 = FakeProvider()
orch5, events5 = build_orch(fake5)
task5 = OrchestratorTask(id="t5", agent_role="nonexistent_agent", user_message="test")
result5 = asyncio.run(orch5.run(task5))
check("status failed", result5.status == "failed", result5.status)
check("error message contains agent", "nonexistent_agent" in result5.error_message)

# Test 6: FakeProvider text responses
print("\nTest 6: FakeProvider")
fake6 = FakeProvider(text_responses=["First", "Second"])
r1 = asyncio.run(fake6.chat(messages=[]))
r2 = asyncio.run(fake6.chat(messages=[]))
check("first response", r1.content == "First", r1.content)
check("second response", r2.content == "Second", r2.content)

# Test 7: FakeProvider tool calls
print("\nTest 7: FakeProvider tool calls")
fake7 = FakeProvider(
    tool_call_scenarios=[[_tc("c1", "search", '{"q":"test"}')]],
    text_responses=["Summary"],
)
r7a = asyncio.run(fake7.chat(messages=[]))
r7b = asyncio.run(fake7.chat(messages=[]))
check("has tool calls", r7a.tool_calls is not None and len(r7a.tool_calls) == 1)
check("tool name", r7a.tool_calls[0].function.name == "search")
check("text response", r7b.content == "Summary")

# Test 8: FakeProvider error injection
print("\nTest 8: FakeProvider error injection")
fake8 = FakeProvider(inject_error_at_round=1)
try:
    asyncio.run(fake8.chat(messages=[]))
    check("should have raised", False, "No exception raised")
except RuntimeError as e:
    check("error raised", "injected" in str(e))

# Summary
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"SOME TESTS FAILED ({failed} failures)")
    sys.exit(1)
