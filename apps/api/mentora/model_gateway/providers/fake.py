"""
FakeProvider：确定性测试用 Provider。

约定：
- 通过预置响应队列模拟 LLM 行为
- 支持纯文本、工具调用和轮次注入错误

约束：
- 不发出任何网络请求
- tool_call_scenarios 的每一项对应一轮对话
- 队列耗尽后返回空 stop 响应

@module mentora/model_gateway/providers/fake
"""

from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.schemas import (
    FunctionCall,
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)


class FakeProvider(BaseProvider):
    """确定性测试用的模型提供方。

    使用方式：
    ```python
    fake = FakeProvider(
        text_responses=["第一轮回复", "第二轮回复"],
        tool_call_scenarios=[
            [ToolCall(id="call_1", function=FunctionCall(name="retrieve", arguments='{"q":"x"}'))],
            [],
        ],
    )
    ```
    """

    name = "fake"
    default_model = "fake-model-v1"

    def __init__(
        self,
        text_responses: list[str] | None = None,
        tool_call_scenarios: list[list[ToolCall]] | None = None,
        inject_error_at_round: int | None = None,
    ):
        self._texts: list[str] = text_responses or []
        self._tool_scenarios: list[list[ToolCall]] = tool_call_scenarios or []
        self._inject_error_round = inject_error_at_round
        self._round = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> ProviderResponse:
        """返回预置响应，按轮次递增。"""
        self._round += 1
        round_idx = self._round - 1

        if self._inject_error_round == self._round:
            raise RuntimeError(f"FakeProvider injected error at round {self._round}")

        # 工具调用优先
        if round_idx < len(self._tool_scenarios):
            tool_calls = self._tool_scenarios[round_idx]
            return ProviderResponse(
                content=None,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
                model=model or self.default_model,
            )

        # 纯文本响应
        text = (
            self._texts[round_idx - len(self._tool_scenarios)]
            if round_idx - len(self._tool_scenarios) < len(self._texts)
            else ""
        )
        return ProviderResponse(
            content=text,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=len(text) // 4, total_tokens=100 + len(text) // 4),
            model=model or self.default_model,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
    ):
        """流式模式：将文本/工具调用拆分为逐 chunk 输出。

        约定：
        - 工具调用轮次：第一个 chunk 返回 tool_calls，最后一个 chunk 为空 stop
        - 文本轮次：字符串逐字符 4 个字符一组输出
        - 错误注入轮次：直接抛出异常
        """
        self._round += 1
        round_idx = self._round - 1

        if self._inject_error_round == self._round:
            raise RuntimeError(f"FakeProvider injected error at round {self._round}")

        # 工具调用场景
        if round_idx < len(self._tool_scenarios):
            tool_calls = self._tool_scenarios[round_idx]
            # 第一个 chunk：tool_calls + streaming finish_reason
            yield ProviderResponse(
                content=None,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason="tool_calls" if tool_calls else "stop",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
                model=model or self.default_model,
            )
            return

        # 纯文本场景：按字符分组流式输出
        text_idx = round_idx - len(self._tool_scenarios)
        text = (
            self._texts[text_idx]
            if text_idx < len(self._texts)
            else ""
        )
        chunk_size = 4
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i : i + chunk_size]
            yield ProviderResponse(
                content=chunk_text,
                finish_reason="streaming",
                model=model or self.default_model,
            )

        # 最后一个 chunk：stop + usage
        yield ProviderResponse(
            content=None,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=len(text) // 4,
                total_tokens=100 + len(text) // 4,
            ),
            model=model or self.default_model,
        )

    def reset(self) -> None:
        """重置轮次计数器。"""
        self._round = 0
