"""
模型 Provider 抽象基类。

约定：
- 所有 Provider 实现 chat() 异步方法
- chat_stream() 为可选流式方法
- Provider 不负责路由和审计（由 ModelGateway 负责）

@module mentora/model_gateway/providers/base
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from mentora.model_gateway.schemas import Message, ProviderResponse


class BaseProvider(ABC):
    """模型提供方抽象基类。

    约束：
    - chat() 接收消息列表和可选 tools，返回统一 ProviderResponse
    - chat_stream() 为可选方法，默认抛出 NotImplementedError
    - 错误通过异常传播，不吞没
    """

    name: str = "base"
    default_model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> ProviderResponse:
        """发送聊天请求到模型提供方。

        参数：
        - messages: 对话消息列表
        - tools: Function Calling 工具定义（OpenAI 格式）
        - model: 覆盖 default_model

        返回：统一 ProviderResponse
        """
        ...

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[ProviderResponse, None]:
        """流式聊天完成（可选方法）。

        默认抛出 NotImplementedError。不支持流式的 Provider 保持默认即可。

        参数：
        - messages: 对话消息列表
        - tools: Function Calling 工具定义（OpenAI 格式）
        - model: 覆盖 default_model

        Yields：逐 chunk 的 ProviderResponse
        """
        raise NotImplementedError(f"{self.name} provider does not support streaming")
