"""DeepSeek DSML 工具调用解析与流式过滤测试。"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from django.test import SimpleTestCase

from mentora.agent_runtime.agents.base import AgentInput
from mentora.agent_runtime.agents.turn_loop import run_tool_loop_stream
from mentora.agent_runtime.schemas.context import AgentContext, ContextAllocation
from mentora.model_gateway.dsml_tool_calls import (
    DsmlStreamFilter,
    parse_dsml_tool_calls,
)
from mentora.model_gateway.providers.openai import OpenAIProvider
from mentora.model_gateway.schemas import Message, ProviderResponse, TokenUsage


class ParseDsmlToolCallsTests(SimpleTestCase):
    def test_parses_user_reported_example(self):
        content = (
            '<｜｜DSML｜｜tool_calls>\n'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">\n'
            '<｜｜DSML｜｜parameter name="query" string="true">'
            "操作系统 定义 计算机系统 管理 硬件 软件 资源"
            "</｜｜DSML｜｜parameter>\n"
            '<｜｜DSML｜｜parameter name="top_k" string="false">3</｜｜DSML｜｜parameter>\n'
            "</｜｜DSML｜｜invoke>\n"
            "</｜｜DSML｜｜tool_calls>"
        )
        cleaned, tool_calls = parse_dsml_tool_calls(content)
        self.assertIsNone(cleaned)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].function.name, "retrieve_evidence")
        self.assertIn("操作系统", tool_calls[0].function.arguments)
        self.assertIn('"top_k": 3', tool_calls[0].function.arguments)

    def test_keeps_prefix_before_dsml(self):
        content = (
            "我先查一下资料。\n"
            "<｜DSML｜tool_calls>"
            '<｜DSML｜invoke name="retrieve_evidence">'
            '<｜DSML｜parameter name="query" string="true">test</｜DSML｜parameter>'
            "</｜DSML｜invoke>"
            "</｜DSML｜tool_calls>"
        )
        cleaned, tool_calls = parse_dsml_tool_calls(content)
        self.assertEqual(cleaned, "我先查一下资料。")
        self.assertEqual(len(tool_calls), 1)

    def test_no_promotion_when_disabled(self):
        content = (
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )
        cleaned, tool_calls = parse_dsml_tool_calls(content, allow_promotion=False)
        self.assertEqual(cleaned, "")
        self.assertEqual(tool_calls, [])

    def test_no_promotion_keeps_prefix(self):
        content = (
            "再补充检索一下完整定义。"
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )
        cleaned, tool_calls = parse_dsml_tool_calls(content, allow_promotion=False)
        self.assertEqual(cleaned, "再补充检索一下完整定义。")
        self.assertEqual(tool_calls, [])


class DsmlStreamFilterTests(SimpleTestCase):
    def test_filters_complete_dsml_block_from_stream(self):
        dsml = (
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )
        filt = DsmlStreamFilter()
        emitted: list[str] = []
        for idx in range(0, len(dsml), 12):
            emitted.extend(filt.push(dsml[idx : idx + 12]))
        emitted.extend(filt.flush())
        self.assertEqual("".join(emitted), "")

    def test_emits_prefix_before_dsml(self):
        filt = DsmlStreamFilter()
        chunks = filt.push("你好！") + filt.push(
            '<｜DSML｜tool_calls><｜DSML｜invoke name="x"></｜DSML｜invoke></｜DSML｜tool_calls>'
        )
        chunks.extend(filt.flush())
        self.assertEqual("".join(chunks), "你好！")


class TurnLoopDsmlRecoveryTests(SimpleTestCase):
    def test_streaming_dsml_content_is_executed_not_shown(self):
        gateway = MagicMock()
        emitted: list[str] = []
        dsml = (
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )

        async def fake_chat_stream(**kwargs: Any):
            for idx in range(0, len(dsml), 20):
                yield MagicMock(
                    content=dsml[idx : idx + 20],
                    tool_calls=None,
                    usage=TokenUsage(),
                )

        async def fake_chat(**kwargs: Any):
            return MagicMock(
                content="操作系统是管理软硬件资源的系统软件。",
                tool_calls=None,
                usage=TokenUsage(),
            )

        gateway.chat_stream = fake_chat_stream
        gateway.chat = fake_chat

        registry = MagicMock()
        registry.get_openai_tools.return_value = [
            {"type": "function", "function": {"name": "retrieve_evidence"}},
        ]
        registry.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                result={"results": [{"content_preview": "操作系统定义", "page_number": 1}]},
                error="",
                duration_ms=1.0,
            )
        )

        emitter = MagicMock()
        emitter.agent_response_stream = lambda _task_id, content, is_final=False: emitted.append(content)

        agent_input = AgentInput(
            task_id="task-dsml",
            user_message="操作系统是什么",
            context=AgentContext(
                messages=[Message(role="user", content="操作系统是什么")],
                system_prompt="system",
                allocation=ContextAllocation(),
            ),
            max_tool_rounds=3,
            tool_metadata={"allow_retrieval": True, "allow_progress": True},
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
        self.assertIn("操作系统", output.final_message)
        self.assertNotIn("DSML", "".join(emitted))
        registry.execute.assert_awaited()


class OpenAIProviderDsmlTests(SimpleTestCase):
    def test_tools_empty_does_not_promote_dsml(self):
        provider = OpenAIProvider(api_key="test")
        dsml = (
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )
        response = provider._apply_dsml_fallback(
            ProviderResponse(content=dsml, finish_reason="stop", usage=TokenUsage(), model="test"),
            tools=None,
        )
        self.assertIsNone(response.tool_calls)
        self.assertEqual(response.content, "")

    def test_tools_present_promotes_dsml(self):
        provider = OpenAIProvider(api_key="test")
        dsml = (
            '<｜｜DSML｜｜tool_calls>'
            '<｜｜DSML｜｜invoke name="retrieve_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">操作系统</｜｜DSML｜｜parameter>'
            "</｜｜DSML｜｜invoke>"
            "</｜｜DSML｜｜tool_calls>"
        )
        response = provider._apply_dsml_fallback(
            ProviderResponse(content=dsml, finish_reason="stop", usage=TokenUsage(), model="test"),
            tools=[{"type": "function", "function": {"name": "retrieve_evidence"}}],
        )
        self.assertEqual(len(response.tool_calls or []), 1)
        self.assertEqual(response.tool_calls[0].function.name, "retrieve_evidence")
