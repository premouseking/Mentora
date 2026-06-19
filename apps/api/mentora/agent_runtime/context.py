"""
Agent 上下文管理：history 维护、token 估算与 prompt 组装。

约定：
- for_prompt() 只返回对话 history（user/assistant/tool），不含 system instructions。
- system instructions 由 PromptBuilder 单独生成，在 loop 层前置拼接。

@see docs/architecture/technical-solution.md §8
@module mentora/agent_runtime/context
"""

from __future__ import annotations

from mentora.model_gateway.contracts import ModelMessage, Role

from .contracts import AgentMessage
from .exceptions import ContextBudgetExceeded


class ContextManager:
    def __init__(self, *, token_budget: int = 32_000) -> None:
        self._history: list[AgentMessage] = []
        self._token_budget = token_budget

    @property
    def history(self) -> list[AgentMessage]:
        return list(self._history)

    def record(self, messages: list[AgentMessage]) -> None:
        self._history.extend(messages)

    def estimate_tokens(self, extra_text: str = "") -> int:
        """启发式 token 估算（字节/4），与 codex 本地估算口径类似。"""
        total_chars = len(extra_text)
        for message in self._history:
            total_chars += len(message.content)
            for call in message.tool_calls:
                total_chars += len(call.arguments) + len(call.name)
        return max(1, total_chars // 4)

    def maybe_compact(self) -> bool:
        """
        上下文压缩 hook。

        首版不实现 LLM 摘要；超预算时显式失败，避免静默把过长上下文交给模型。
        后续可接入 lightest/codex 式 compaction。
        """
        if self.estimate_tokens() <= self._token_budget:
            return False
        raise ContextBudgetExceeded("上下文超过 token 预算，当前版本尚未接入自动压缩")

    def for_prompt(self) -> list[ModelMessage]:
        """将 agent history 桥接为 model_gateway 消息列表。"""
        return [self._to_model_message(message) for message in self._history]

    @staticmethod
    def _to_model_message(message: AgentMessage) -> ModelMessage:
        role = Role(message.role)
        return ModelMessage(
            role=role,
            content=message.content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
