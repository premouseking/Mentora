"""
模型网关契约测试：async chat / chat_stream、结构化校验、重试与 Fallback。
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from mentora.model_gateway.exceptions import ProviderError, StructuredOutputError
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.fake import FakeProvider, make_tool_call
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import Message
from mentora.model_gateway.structured_output import StructuredOutputValidator


class _Shape(BaseModel):
    message: str


class _FailThenOk(FakeProvider):
    """第一次失败，第二次成功。"""

    def __init__(self, ok_text: str):
        super().__init__(text_responses=[ok_text])
        self._calls = 0

    async def chat(self, messages, tools=None, model=None):
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("transient")
        return await super().chat(messages, tools, model)


def _gateway(provider=None, *, max_retries: int = 1) -> ModelGateway:
    provider = provider or FakeProvider(text_responses=["你好"])
    return ModelGateway(
        router=TaskRouter(default_provider=provider),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
        max_retries_per_attempt=max_retries,
    )


@pytest.mark.asyncio
async def test_chat_text_response():
    gateway = _gateway(FakeProvider(text_responses=["你好世界"]))
    resp = await gateway.chat(
        task_type="test",
        messages=[Message(role="user", content="hi")],
    )
    assert resp.content == "你好世界"
    assert resp.finish_reason == "stop"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_chat_structured_output_valid():
    gateway = _gateway(FakeProvider(text_responses=['{"message": "ok"}']))
    resp = await gateway.chat(
        task_type="test",
        messages=[Message(role="user", content="hi")],
        structured_output_schema=_Shape,
    )
    assert resp.parsed_output == {"message": "ok"}


@pytest.mark.asyncio
async def test_chat_structured_invalid_raises():
    gateway = _gateway(FakeProvider(text_responses=["not json"]))
    with pytest.raises(StructuredOutputError):
        await gateway.chat(
            task_type="test",
            messages=[Message(role="user", content="hi")],
            structured_output_schema=_Shape,
        )


@pytest.mark.asyncio
async def test_chat_retries_on_provider_error():
    gateway = ModelGateway(
        router=TaskRouter(default_provider=_FailThenOk("恢复")),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
        max_retries_per_attempt=1,
    )
    resp = await gateway.chat(
        task_type="test",
        messages=[Message(role="user", content="hi")],
    )
    assert resp.content == "恢复"


@pytest.mark.asyncio
async def test_chat_fallback_provider():
    primary = FakeProvider(inject_error_at_round=1)
    secondary = FakeProvider(text_responses=["来自备选"])
    router = TaskRouter(default_provider=primary)
    router.register_candidates("test", [primary, secondary])
    gateway = ModelGateway(
        router=router,
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
        max_retries_per_attempt=0,
    )
    resp = await gateway.chat(
        task_type="test",
        messages=[Message(role="user", content="hi")],
    )
    assert resp.content == "来自备选"


@pytest.mark.asyncio
async def test_chat_all_fail_raises():
    primary = FakeProvider(inject_error_at_round=1)
    gateway = ModelGateway(
        router=TaskRouter(default_provider=primary),
        output_validator=StructuredOutputValidator(),
        audit_enabled=False,
        max_retries_per_attempt=0,
    )
    with pytest.raises(ProviderError):
        await gateway.chat(
            task_type="test",
            messages=[Message(role="user", content="hi")],
        )


@pytest.mark.asyncio
async def test_chat_stream_emits_chunks():
    fake = FakeProvider(text_responses=["你好世界"])
    gateway = _gateway(fake)
    chunks = []
    async for chunk in gateway.chat_stream(
        task_type="test",
        messages=[Message(role="user", content="hi")],
    ):
        chunks.append(chunk)
    text = "".join(c.content or "" for c in chunks)
    assert "你好世界" in text
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_chat_with_tool_calls():
    fake = FakeProvider(
        tool_call_scenarios=[
            [make_tool_call("c1", "search", '{"q":"test"}')],
        ],
    )
    gateway = _gateway(fake)
    resp = await gateway.chat(
        task_type="test",
        messages=[Message(role="user", content="搜")],
        tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
    )
    assert resp.tool_calls is not None
    assert resp.tool_calls[0].function.name == "search"
