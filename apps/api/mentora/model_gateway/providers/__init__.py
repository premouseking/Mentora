"""
Provider 适配层：把厂商无关的 ProviderRequest 翻译为各家协议并归一化回 ProviderResponse。

约定：
- 新增厂商 = 新增一个 LlmProvider 子类，无需改动网关与领域服务。
- 仅本层允许出现厂商协议细节（endpoint、字段名、鉴权头）。

@module mentora/model_gateway/providers
"""

from .base import (
    LlmProvider,
    ProviderRequest,
    ProviderResponse,
    ProviderStreamChunk,
)
from .fake import FakeProvider
from .openai_compatible import OpenAICompatibleProvider

__all__ = [
    "LlmProvider",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStreamChunk",
    "FakeProvider",
    "OpenAICompatibleProvider",
]
