"""turn_loop 检索后回答轮次测试。"""

import asyncio
from ssl import SSLError
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from django.test import SimpleTestCase

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.agents.turn_loop import (
    _extract_tool_citations,
    _filter_tools_for_turn,
    _format_tool_message_content,
    _resolve_round_tools,
    run_tool_loop_stream,
)
from mentora.agent_runtime.schemas.context import AgentContext, ContextAllocation
from mentora.agent_runtime.schemas.output import ToolInvocationRecord
from mentora.model_gateway.schemas import ChatResponse, FunctionCall, Message, TokenUsage, ToolCall


class ResolveRoundToolsTests(SimpleTestCase):
    def test_disables_tools_after_tool_records_exist(self):
        tools = [{"type": "function", "function": {"name": "retrieve_evidence"}}]
        records = [
            ToolInvocationRecord(tool_name="retrieve_evidence", arguments={}, success=True),
        ]
        self.assertIsNone(
            _resolve_round_tools(
                tools,
                round_num=1,
                max_tool_rounds=3,
                tool_records=records,
            )
        )


class FilterToolsForTurnTests(SimpleTestCase):
    def test_metadata_disables_retrieval_tool(self):
        tools = [
            {"type": "function", "function": {"name": "retrieve_evidence"}},
            {"type": "function", "function": {"name": "get_learning_progress"}},
        ]
        filtered = _filter_tools_for_turn(
            tools,
            {"allow_retrieval": False, "allow_progress": True},
        )
        names = [(t.get("function") or {}).get("name") for t in filtered]
        self.assertEqual(names, ["get_learning_progress"])

    def test_metadata_disables_progress_tool(self):
        tools = [
            {"type": "function", "function": {"name": "retrieve_evidence"}},
            {"type": "function", "function": {"name": "get_learning_progress"}},
        ]
        filtered = _filter_tools_for_turn(
            tools,
            {"allow_retrieval": True, "allow_progress": False},
        )
        names = [(t.get("function") or {}).get("name") for t in filtered]
        self.assertEqual(names, ["retrieve_evidence"])


class ToolCitationTests(SimpleTestCase):
    def test_tool_message_hides_evidence_id_from_model(self):
        result = MagicMock(
            tool_name="retrieve_evidence",
            success=True,
            result={
                "query": "操作系统",
                "results": [
                    {
                        "evidence_id": "f1981927",
                        "content": "操作系统是管理计算机硬件与软件资源的系统软件。",
                        "content_preview": "操作系统是管理计算机硬件与软件资源的系统软件。",
                        "page_number": 1,
                    }
                ],
            },
            error="",
            artifact_ref="",
        )

        content = _format_tool_message_content(result)

        self.assertNotIn("evidence_id", content)
        self.assertNotIn("f1981927", content)
        self.assertIn("操作系统是管理计算机硬件与软件资源的系统软件", content)

    def test_citations_include_full_content_without_evidence_id(self):
        result = MagicMock(
            success=True,
            result={
                "results": [
                    {
                        "evidence_id": "secret-id",
                        "content": "操作系统是管理计算机硬件与软件资源的系统软件。",
                        "content_preview": "操作系统是管理计算机硬件与软件资源的系统软件。",
                        "page_number": 3,
                        "source_title": "操作系统讲义",
                    }
                ]
            },
        )

        citations = _extract_tool_citations(result)

        self.assertEqual(len(citations), 1)
        self.assertNotIn("evidence_id", citations[0])
        self.assertEqual(citations[0]["content"], "操作系统是管理计算机硬件与软件资源的系统软件。")
        self.assertEqual(citations[0]["source_title"], "操作系统讲义")


class TurnLoopPostRetrievalTests(SimpleTestCase):
    def test_uses_blocking_chat_after_first_tool_execution(self):
        gateway = MagicMock()
        stream_calls = {"value": 0}
        chat_calls = {"value": 0}
        tools_seen: list[list[dict] | None] = []
        tool_defs = [{"type": "function", "function": {"name": "retrieve_evidence"}}]

        async def fake_chat_stream(**kwargs: Any):
            stream_calls["value"] += 1
            tools_seen.append(kwargs.get("tools"))
            yield ChatResponse(
                content="我先查一下资料。",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="retrieve_evidence",
                            arguments='{"query":"操作系统"}',
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage=TokenUsage(),
                model="test",
            )

        async def fake_chat(**kwargs: Any):
            chat_calls["value"] += 1
            tools_seen.append(kwargs.get("tools"))
            return ChatResponse(
                content="操作系统是管理计算机硬件与软件资源的系统软件。",
                finish_reason="stop",
                usage=TokenUsage(),
                model="test",
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = fake_chat

        registry = MagicMock()
        registry.get_openai_tools.return_value = tool_defs
        registry.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                result={"results": [{"content_preview": "操作系统定义", "page_number": 1}]},
                error="",
                duration_ms=1.0,
            )
        )

        agent_input = AgentInput(
            task_id="task-post-tool",
            user_message="操作系统是什么",
            context=AgentContext(
                messages=[Message(role="user", content="操作系统是什么")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
        )

        output = asyncio.run(
            run_tool_loop_stream(
                agent_role="tutor",
                agent_input=agent_input,
                registry=registry,
                gateway=gateway,
                emitter=None,
            )
        )

        self.assertEqual(output.finish_reason, "completed")
        self.assertIn("操作系统", output.final_message)
        self.assertEqual(stream_calls["value"], 1)
        self.assertEqual(chat_calls["value"], 1)
        self.assertEqual(tools_seen[0], tool_defs)
        self.assertIsNone(tools_seen[1])

    def test_tool_preamble_is_not_streamed_before_status(self):
        gateway = MagicMock()
        events: list[tuple[str, str]] = []
        tool_defs = [{"type": "function", "function": {"name": "retrieve_evidence"}}]

        async def fake_chat_stream(**kwargs: Any):
            yield ChatResponse(
                content="好的，让我在课程资料中检索操作系统的定义！",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="retrieve_evidence",
                            arguments='{"query":"操作系统"}',
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage=TokenUsage(),
                model="test",
            )

        async def fake_chat(**kwargs: Any):
            return ChatResponse(
                content="操作系统是管理计算机硬件与软件资源的系统软件。",
                finish_reason="stop",
                usage=TokenUsage(),
                model="test",
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = fake_chat

        registry = MagicMock()
        registry.get_openai_tools.return_value = tool_defs
        registry.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                result={"results": [{"content": "操作系统定义", "page_number": 1}]},
                error="",
                duration_ms=1.0,
            )
        )

        emitter = MagicMock()
        emitter.agent_response_stream = lambda _task_id, content, is_final=False: events.append(("chunk", content))
        emitter.tool_call = lambda _task_id, _tool_name, _args: events.append(("status", "正在检索资料"))
        emitter.tool_result = lambda *_args, **_kwargs: events.append(("status", "资料检索完成"))

        agent_input = AgentInput(
            task_id="task-tool-order",
            user_message="操作系统是什么",
            context=AgentContext(
                messages=[Message(role="user", content="操作系统是什么")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
        )

        output = asyncio.run(
            run_tool_loop_stream(
                agent_role="tutor",
                agent_input=agent_input,
                registry=registry,
                gateway=gateway,
                emitter=emitter,
            )
        )

        self.assertEqual(output.finish_reason, "completed")
        visible = [content for kind, content in events if kind == "chunk"]
        self.assertNotIn("好的，让我在课程资料中检索操作系统的定义！", "".join(visible))
        self.assertEqual(events[0], ("status", "正在检索资料"))
        self.assertIn("操作系统是管理", "".join(visible))

    def test_stream_error_with_tool_calls_still_executes_tools(self):
        gateway = MagicMock()
        chat_calls = {"value": 0}
        tool_defs = [{"type": "function", "function": {"name": "retrieve_evidence"}}]

        async def fake_chat_stream(**kwargs: Any):
            yield ChatResponse(
                content="我先查一下资料。",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="retrieve_evidence",
                            arguments='{"query":"操作系统"}',
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage=TokenUsage(),
                model="test",
            )
            raise SSLError("stream interrupted")

        async def fake_chat(**kwargs: Any):
            chat_calls["value"] += 1
            return ChatResponse(
                content="基于检索结果，操作系统是管理软硬件资源的系统软件。",
                finish_reason="stop",
                usage=TokenUsage(),
                model="test",
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = fake_chat

        registry = MagicMock()
        registry.get_openai_tools.return_value = tool_defs
        registry.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                result={"results": [{"content_preview": "操作系统定义", "page_number": 1}]},
                error="",
                duration_ms=1.0,
            )
        )

        agent_input = AgentInput(
            task_id="task-stream-error",
            user_message="操作系统是什么",
            context=AgentContext(
                messages=[Message(role="user", content="操作系统是什么")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
        )

        output = asyncio.run(
            run_tool_loop_stream(
                agent_role="tutor",
                agent_input=agent_input,
                registry=registry,
                gateway=gateway,
                emitter=None,
            )
        )

        self.assertEqual(output.finish_reason, "completed")
        self.assertEqual(chat_calls["value"], 1)

    def test_smalltalk_metadata_excludes_retrieval_from_gateway(self):
        gateway = MagicMock()
        tools_seen: list[list[dict] | None] = []
        tool_defs = [
            {"type": "function", "function": {"name": "retrieve_evidence"}},
            {"type": "function", "function": {"name": "get_learning_progress"}},
        ]

        async def fake_chat_stream(**kwargs: Any):
            tools_seen.append(kwargs.get("tools"))
            yield ChatResponse(
                content="你好！有什么我可以帮你的吗？",
                finish_reason="stop",
                usage=TokenUsage(),
                model="test",
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = AsyncMock()

        registry = MagicMock()
        registry.get_openai_tools.return_value = tool_defs
        registry.execute = AsyncMock()

        agent_input = AgentInput(
            task_id="task-smalltalk",
            user_message="你好",
            context=AgentContext(
                messages=[Message(role="user", content="你好")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
            tool_metadata={"allow_retrieval": False, "allow_progress": True},
        )

        output = asyncio.run(
            run_tool_loop_stream(
                agent_role="tutor",
                agent_input=agent_input,
                registry=registry,
                gateway=gateway,
                emitter=None,
            )
        )

        self.assertEqual(output.finish_reason, "completed")
        self.assertEqual(len(tools_seen), 1)
        names = [
            (tool.get("function") or {}).get("name")
            for tool in (tools_seen[0] or [])
        ]
        self.assertNotIn("retrieve_evidence", names)
        self.assertIn("get_learning_progress", names)
        registry.execute.assert_not_called()

    def test_post_retrieval_dsml_does_not_trigger_second_retrieval(self):
        gateway = MagicMock()
        chat_calls = {"value": 0}
        tool_defs = [{"type": "function", "function": {"name": "retrieve_evidence"}}]
        dsml = (
            "再补充检索一下完整定义。"
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统 定义</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )

        async def fake_chat_stream(**kwargs: Any):
            yield ChatResponse(
                content="我先查一下资料。",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="retrieve_evidence",
                            arguments='{"query":"操作系统"}',
                        ),
                    )
                ],
                finish_reason="tool_calls",
                usage=TokenUsage(),
                model="test",
            )

        async def fake_chat(**kwargs: Any):
            chat_calls["value"] += 1
            if chat_calls["value"] == 1:
                return ChatResponse(
                    content=dsml,
                    finish_reason="stop",
                    usage=TokenUsage(),
                    model="test",
                )
            return ChatResponse(
                content="操作系统是管理计算机硬件与软件资源的系统软件，负责进程调度、内存管理与文件系统。",
                finish_reason="stop",
                usage=TokenUsage(),
                model="test",
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = fake_chat

        registry = MagicMock()
        registry.get_openai_tools.return_value = tool_defs
        registry.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                result={"results": [{"content_preview": "操作系统定义", "page_number": 1}]},
                error="",
                duration_ms=1.0,
            )
        )

        agent_input = AgentInput(
            task_id="task-dsml-final",
            user_message="请解释一下什么是操作系统",
            context=AgentContext(
                messages=[Message(role="user", content="请解释一下什么是操作系统")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
        )

        output = asyncio.run(
            run_tool_loop_stream(
                agent_role="tutor",
                agent_input=agent_input,
                registry=registry,
                gateway=gateway,
                emitter=None,
            )
        )

        self.assertEqual(output.finish_reason, "completed")
        self.assertIn("操作系统", output.final_message)
        self.assertEqual(chat_calls["value"], 2)
        registry.execute.assert_awaited_once()
