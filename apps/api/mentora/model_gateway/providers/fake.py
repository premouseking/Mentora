"""Deterministic fake provider for sync and async gateway tests."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from mentora.model_gateway.contracts import TokenUsage as LegacyTokenUsage
from mentora.model_gateway.contracts import ToolCall as LegacyToolCall
from mentora.model_gateway.providers.base import (
    BaseProvider,
    LlmProvider,
    ProviderRequest,
    ProviderResponse,
    ProviderStreamChunk,
)
from mentora.model_gateway.schemas import (
    FunctionCall,
    Message,
    ProviderResponse as AsyncProviderResponse,
    TokenUsage,
    ToolCall,
)


class FakeProvider(LlmProvider, BaseProvider):
    name = "fake"
    default_model = "fake-model-v1"

    def __init__(
        self,
        *,
        name: str = "fake",
        script: Sequence[ProviderResponse | str | Exception | list] | None = None,
        default_text: str = '{"ok": true}',
        text_responses: list[str] | None = None,
        tool_call_scenarios: list[list[ToolCall]] | None = None,
        inject_error_at_round: int | None = None,
    ) -> None:
        self.name = name
        self.default_model = "fake-model-v1"
        self._script: list[ProviderResponse | str | Exception | list] = list(script or [])
        self._default_text = default_text
        self._texts = text_responses or []
        self._tool_scenarios = tool_call_scenarios or []
        self._inject_error_round = inject_error_at_round
        self._index = 0
        self._round = 0
        self.calls: list[ProviderRequest] = []

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.calls.append(request)
        step = self._next_sync_step()
        if isinstance(step, Exception):
            raise step
        if isinstance(step, ProviderResponse):
            return ProviderResponse(
                text=step.text,
                model=step.model or request.model,
                finish_reason=step.finish_reason,
                usage=step.usage,
                tool_calls=step.tool_calls,
            )
        return self._wrap_sync(str(step), request.model)

    def stream(self, request: ProviderRequest) -> Iterator[ProviderStreamChunk]:
        self.calls.append(request)
        step = self._next_sync_step()
        if isinstance(step, Exception):
            raise step
        if isinstance(step, (list, tuple)):
            for chunk in step:
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
            return
        if isinstance(step, ProviderResponse):
            if step.tool_calls:
                yield ProviderStreamChunk(
                    finish_reason=step.finish_reason,
                    usage=step.usage,
                    tool_calls=list(step.tool_calls),
                )
                return
            text = step.text
            usage = step.usage
            finish_reason = step.finish_reason
        else:
            text = str(step)
            usage = LegacyTokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
            finish_reason = "stop"

        for char in text:
            yield ProviderStreamChunk(delta=char)
        yield ProviderStreamChunk(finish_reason=finish_reason, usage=usage)

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncProviderResponse:
        self._round += 1
        if self._inject_error_round == self._round:
            raise RuntimeError(f"FakeProvider injected error at round {self._round}")

        round_idx = self._round - 1
        if round_idx < len(self._tool_scenarios):
            tool_calls = self._tool_scenarios[round_idx]
            return AsyncProviderResponse(
                content=None,
                tool_calls=tool_calls or None,
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
                model=model or self.default_model,
            )

        text_idx = round_idx - len(self._tool_scenarios)
        text = self._texts[text_idx] if text_idx < len(self._texts) else ""
        return AsyncProviderResponse(
            content=text,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=len(text) // 4,
                total_tokens=100 + len(text) // 4,
            ),
            model=model or self.default_model,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ):
        response = await self.chat(messages, tools, model)
        if response.tool_calls:
            yield response
            return

        text = response.content or ""
        for i in range(0, len(text), 4):
            yield AsyncProviderResponse(
                content=text[i : i + 4],
                finish_reason="streaming",
                model=response.model,
            )
        yield AsyncProviderResponse(
            content=None,
            finish_reason="stop",
            usage=response.usage,
            model=response.model,
        )

    def reset(self) -> None:
        self._index = 0
        self._round = 0
        self.calls.clear()

    def _next_sync_step(self) -> ProviderResponse | str | Exception | list:
        if self._index < len(self._script):
            step = self._script[self._index]
            self._index += 1
            return step
        return self._default_text

    @staticmethod
    def _wrap_sync(text: str, model: str) -> ProviderResponse:
        return ProviderResponse(
            text=text,
            model=model,
            finish_reason="stop",
            usage=LegacyTokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            tool_calls=[],
        )


def legacy_tool_call_to_async(call: LegacyToolCall) -> ToolCall:
    return ToolCall(
        id=call.id,
        function=FunctionCall(name=call.name, arguments=call.arguments),
    )
