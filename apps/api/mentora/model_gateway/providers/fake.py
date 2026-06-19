"""
确定性 Fake Provider，供测试与离线开发使用。

约定（借鉴 lightest 的 fakeLlm）：
- 不需要任何外部凭证或网络，用于契约测试与 CI。
- 支持按「脚本」逐轮返回，或注入异常以验证网关的重试/Fallback 决策。

@module mentora/model_gateway/providers/fake
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from ..contracts import TokenUsage, ToolCall
from .base import LlmProvider, ProviderRequest, ProviderResponse, ProviderStreamChunk


class FakeProvider(LlmProvider):
    def __init__(
        self,
        *,
        name: str = "fake",
        # 每轮可为 ProviderResponse、纯文本（自动包装）或 Exception（抛出）。
        script: Sequence[ProviderResponse | str | Exception] | None = None,
        default_text: str = '{"ok": true}',
    ) -> None:
        self.name = name
        self._script: list[ProviderResponse | str | Exception] = list(script or [])
        self._default_text = default_text
        self._index = 0
        # 记录收到的请求，便于断言路由结果（如实际选用的模型）。
        self.calls: list[ProviderRequest] = []

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.calls.append(request)

        if self._index < len(self._script):
            step = self._script[self._index]
            self._index += 1
            if isinstance(step, Exception):
                raise step
            if isinstance(step, str):
                return self._wrap(step, request.model)
            return step

        return self._wrap(self._default_text, request.model)

    def _wrap(self, text: str, model: str) -> ProviderResponse:
        return ProviderResponse(
            text=text,
            model=model,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            tool_calls=[],
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderStreamChunk]:
        self.calls.append(request)

        step: object = self._default_text
        if self._index < len(self._script):
            step = self._script[self._index]
            self._index += 1

        # 流开始前即失败：用于验证「首片前可 Fallback」。
        if isinstance(step, Exception):
            raise step

        # 显式分片序列：元素为 Exception 时模拟「流中途断开」。
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
            finish_reason = step.finish_reason
            usage = step.usage
        else:
            text = str(step)
            finish_reason = "stop"
            usage = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        for char in text:
            yield ProviderStreamChunk(delta=char)
        yield ProviderStreamChunk(finish_reason=finish_reason, usage=usage)
