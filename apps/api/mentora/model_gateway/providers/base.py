"""Async provider protocol for ModelGateway."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from mentora.model_gateway.schemas import Message, ProviderResponse


class BaseProvider(ABC):
    name: str = "base"
    default_model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[ProviderResponse, None]:
        raise NotImplementedError(f"{self.name} provider does not support streaming")
