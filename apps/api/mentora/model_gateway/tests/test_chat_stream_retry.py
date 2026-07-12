"""ModelGateway.chat_stream 重试与 fallback 测试。"""

import asyncio
from ssl import SSLError
from typing import AsyncGenerator

from django.test import SimpleTestCase

from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import Message, ProviderResponse, TokenUsage


class _FailThenStreamProvider(BaseProvider):
    name = "fail_then_ok"
    default_model = "configured-model"

    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
        *,
        timeout: int | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[ProviderResponse, None]:
        self.calls += 1
        if self.calls == 1:
            raise SSLError("handshake failed")
        yield ProviderResponse(
            content="回答正文",
            finish_reason="streaming",
            model=model or "stream-model",
        )
        yield ProviderResponse(
            content=None,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            model=model or "stream-model",
        )


class _PartialThenFailProvider(BaseProvider):
    name = "partial_fail"
    default_model = "configured-model"

    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
        *,
        timeout: int | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[ProviderResponse, None]:
        self.calls += 1
        yield ProviderResponse(content="partial", finish_reason="streaming", model="stream-model")
        raise SSLError("stream interrupted")


class ChatStreamRetryTests(SimpleTestCase):
    def test_retries_when_stream_fails_before_any_output(self):
        provider = _FailThenStreamProvider()
        gateway = ModelGateway(
            router=TaskRouter(default_provider=provider),
            audit_enabled=False,
            max_retries_per_attempt=1,
        )

        async def collect() -> list[str]:
            chunks: list[str] = []
            async for chunk in gateway.chat_stream(
                task_type="tutor",
                messages=[Message(role="user", content="hello")],
                model="requested-model",
            ):
                if chunk.content:
                    chunks.append(chunk.content)
            return chunks

        chunks = asyncio.run(collect())
        self.assertEqual(chunks, ["回答正文"])
        self.assertEqual(provider.calls, 2)

    def test_does_not_retry_after_partial_stream_output(self):
        provider = _PartialThenFailProvider()
        gateway = ModelGateway(
            router=TaskRouter(default_provider=provider),
            audit_enabled=False,
            max_retries_per_attempt=2,
        )

        async def collect() -> None:
            chunks: list[str] = []
            async for chunk in gateway.chat_stream(
                task_type="tutor",
                messages=[Message(role="user", content="hello")],
            ):
                if chunk.content:
                    chunks.append(chunk.content)

        with self.assertRaises(SSLError):
            asyncio.run(collect())
        self.assertEqual(provider.calls, 1)

    def test_resolve_audit_model_name_prefers_response_model(self):
        provider = _FailThenStreamProvider()
        model_name = ModelGateway._resolve_audit_model_name(
            provider,
            "requested-model",
            None,
        )
        self.assertEqual(model_name, "requested-model")
