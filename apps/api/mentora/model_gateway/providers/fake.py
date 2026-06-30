"""Deterministic fake provider for async gateway tests."""

from __future__ import annotations

from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.schemas import (
    FunctionCall,
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)


class FakeProvider(BaseProvider):
    name = "fake"
    default_model = "fake-model-v1"

    def __init__(
        self,
        *,
        name: str = "fake",
        text_responses: list[str] | None = None,
        tool_call_scenarios: list[list[ToolCall]] | None = None,
        inject_error_at_round: int | None = None,
    ) -> None:
        self.name = name
        self.default_model = "fake-model-v1"
        self._texts = text_responses or []
        self._tool_scenarios = tool_call_scenarios or []
        self._inject_error_round = inject_error_at_round
        self._round = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> ProviderResponse:
        self._round += 1
        if self._inject_error_round == self._round:
            raise RuntimeError(f"FakeProvider injected error at round {self._round}")

        round_idx = self._round - 1
        if round_idx < len(self._tool_scenarios):
            tool_calls = self._tool_scenarios[round_idx]
            return ProviderResponse(
                content=None,
                tool_calls=tool_calls or None,
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
                model=model or self.default_model,
            )

        text_idx = round_idx - len(self._tool_scenarios)
        text = self._texts[text_idx] if text_idx < len(self._texts) else ""
        return ProviderResponse(
            content=text,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=max(1, len(text) // 4),
                total_tokens=100 + max(1, len(text) // 4),
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
            yield ProviderResponse(
                content=text[i : i + 4],
                finish_reason="streaming",
                model=response.model,
            )
        yield ProviderResponse(
            content=None,
            finish_reason="stop",
            usage=response.usage,
            model=response.model,
        )

    def reset(self) -> None:
        self._round = 0


def make_tool_call(call_id: str, name: str, args: str) -> ToolCall:
    """测试辅助：构建 ToolCall。"""
    return ToolCall(id=call_id, function=FunctionCall(name=name, arguments=args))
