"""Provider protocols for both legacy sync and new async gateways."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass, field

from mentora.model_gateway.contracts import TokenUsage as LegacyTokenUsage
from mentora.model_gateway.contracts import ToolCall as LegacyToolCall
from mentora.model_gateway.contracts import ToolSpec
from mentora.model_gateway.schemas import Message, ProviderResponse as AsyncProviderResponse


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    messages: list[dict[str, object]]
    max_output_tokens: int
    temperature: float
    json_mode: bool = False
    tools: tuple[ToolSpec, ...] = ()
    tool_choice: str = "auto"
    timeout_s: float = 60.0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    model: str
    finish_reason: str
    usage: LegacyTokenUsage = LegacyTokenUsage()
    tool_calls: list[LegacyToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderStreamChunk:
    delta: str = ""
    finish_reason: str | None = None
    usage: LegacyTokenUsage | None = None
    tool_calls: list[LegacyToolCall] | None = None


class LlmProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    def stream(self, request: ProviderRequest) -> Iterator[ProviderStreamChunk]:
        response = self.generate(request)
        if response.tool_calls:
            yield ProviderStreamChunk(
                finish_reason=response.finish_reason,
                usage=response.usage,
                tool_calls=list(response.tool_calls),
            )
            return
        yield ProviderStreamChunk(
            delta=response.text,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


class BaseProvider(ABC):
    name: str = "base"
    default_model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncProviderResponse:
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[AsyncProviderResponse, None]:
        raise NotImplementedError(f"{self.name} provider does not support streaming")
