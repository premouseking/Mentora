"""
Provider 抽象基类与归一化的请求/响应类型。

约定：
- ProviderRequest / ProviderResponse 是网关与 provider 之间的归一化协议，
  厂商差异消化在 provider 内部，网关只认一种形态。
- generate() 失败时必须抛 ProviderError（transient 标记是否可重试），
  不得返回半成品。

@module mentora/model_gateway/providers/base
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field

from ..contracts import TokenUsage, ToolCall, ToolSpec


@dataclass(frozen=True)
class ProviderRequest:
    """归一化的 provider 调用入参。"""

    model: str
    messages: list[dict[str, str]]
    max_output_tokens: int
    temperature: float
    # 是否要求 JSON 输出（结构化任务由网关置 True）。
    json_mode: bool = False
    tools: tuple[ToolSpec, ...] = ()
    tool_choice: str = "auto"
    timeout_s: float = 60.0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    """归一化的 provider 返回。"""

    text: str
    model: str
    finish_reason: str
    usage: TokenUsage = TokenUsage()
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderStreamChunk:
    """
    归一化的流式分片。

    约定：
    - delta 为本片增量文本，可为空（如仅携带 finish_reason 或 usage 的收尾片）。
    - finish_reason / usage 通常只在末片出现，过程中为 None。
    """

    delta: str = ""
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    # 流结束时携带完整 tool_calls（OpenAI 在末片聚合）。
    tool_calls: list[ToolCall] | None = None


class LlmProvider(ABC):
    """所有厂商适配器的统一接口。"""

    #: 注册名，用于路由表与审计记录。
    name: str = "base"

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """执行一次同步调用。失败抛 ProviderError / ProviderTimeout。"""
        raise NotImplementedError

    def stream(self, request: ProviderRequest) -> Iterator[ProviderStreamChunk]:
        """
        流式调用。默认实现把同步结果降级为分片，保证所有 provider 都「可流式」。

        真正支持原生流式的厂商应覆盖本方法。
        """
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
