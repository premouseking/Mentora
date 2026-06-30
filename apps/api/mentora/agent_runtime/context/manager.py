"""
上下文管理器：按优先级裁剪上下文消息，确保不超预算。

约定：
- 严格按照 Priority 顺序裁剪
- P0（系统提示词）不可裁剪
- P4（较早历史）最先被裁剪

约束：
- 裁剪后保持时间顺序
- 裁剪算法 O(n) 单次扫描
- 不修改原始消息对象

@module mentora/agent_runtime/context/manager
"""

from copy import deepcopy

from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.schemas.context import ContextAllocation
from mentora.agent_runtime.schemas.task import BudgetConfig
from mentora.model_gateway.schemas import Message


class BudgetPriority:
    """上下文裁剪优先级。

    P0 最高（不可裁剪），P4 最低（最先被裁剪）。
    """

    P0_SYSTEM = 0
    P1_USER_QUERY = 1
    P2_RECENT_MSGS = 2
    P3_EVIDENCE = 3
    P4_OLDER_MSGS = 4


class ContextManager:
    """上下文管理器。

    使用方式：
    ```python
    manager = ContextManager(budget_config, counter)
    messages, allocation = manager.build_messages(
        system_prompt="你是...",
        user_message="问题",
        history=[...],
        evidence_texts=["证据1", "证据2"],
    )
    ```
    """

    def __init__(self, budget: BudgetConfig, counter: TokenCounter | None = None):
        self.budget = budget
        self.counter = counter or TokenCounter()

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[Message] | None = None,
        evidence_texts: list[str] | None = None,
    ) -> tuple[list[Message], ContextAllocation]:
        """组装消息列表并控制在预算内。

        返回：(消息列表, 分配信息)
        """
        history = history or []
        evidence_texts = evidence_texts or []

        available = self.budget.available_for_messages

        # P0：系统提示词（固定）
        system_tokens = self.counter.count_system_prompt(system_prompt)

        # P1：当前用户消息（固定）
        user_tokens = self.counter.count(user_message)

        # 剩余预算
        remaining = available - system_tokens - user_tokens

        # 如果连 P0+P1 都不够，仅返回系统提示词 + 截断用户消息
        if remaining < 0:
            truncated_user = self._truncate_text(user_message, available - system_tokens)
            msg_list = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=truncated_user),
            ]
            return msg_list, ContextAllocation(
                system_tokens=system_tokens,
                user_query_tokens=self.counter.count(truncated_user),
                total_tokens=system_tokens + self.counter.count(truncated_user),
                within_budget=False,
            )

        # 分配：先尝试全量历史 + 证据
        history_copy = deepcopy(history)
        history_tokens = self.counter.count_messages(history_copy)
        evidence_tokens = sum(self.counter.count(e) for e in evidence_texts)

        if history_tokens + evidence_tokens <= remaining:
            # 全量可以通过
            evidence_tokens_used = evidence_tokens
            history_tokens_used = history_tokens
        else:
            # 需要裁剪：P4 先裁历史，P3 再裁证据
            # 优先保留最近的 2 条历史
            recent_count = min(2, len(history_copy))
            recent = history_copy[-recent_count:] if recent_count > 0 else []
            older = history_copy[:-recent_count] if recent_count > 0 else history_copy

            recent_tokens = self.counter.count_messages(recent)

            # 先只保留最近消息
            if recent_tokens + evidence_tokens <= remaining:
                history_copy = recent
                evidence_tokens_used = evidence_tokens
                history_tokens_used = recent_tokens
            else:
                # 证据也需截断
                truncated_evidence, evidence_tokens_used = self._truncate_evidence(
                    evidence_texts, remaining - recent_tokens
                )
                history_copy = recent
                history_tokens_used = recent_tokens
                # 替换 evidence_texts 引用（仅用于构建消息）
                evidence_texts = truncated_evidence

        # 组装消息列表
        messages: list[Message] = []

        # 系统提示词
        messages.append(Message(role="system", content=system_prompt))

        # 历史消息
        messages.extend(history_copy)

        # 证据上下文（注入为 system 消息）
        if evidence_texts:
            evidence_block = "\n\n---\n\n".join(
                f"[证据 {i+1}] {e}" for i, e in enumerate(evidence_texts)
            )
            messages.append(Message(role="system", content=evidence_block))

        # 当前用户消息
        messages.append(Message(role="user", content=user_message))

        total = system_tokens + user_tokens + history_tokens_used + evidence_tokens_used

        return messages, ContextAllocation(
            system_tokens=system_tokens,
            user_query_tokens=user_tokens,
            history_tokens=history_tokens_used,
            evidence_tokens=evidence_tokens_used,
            total_tokens=total,
            within_budget=total <= available,
        )

    def _truncate_evidence(
        self, texts: list[str], available: int
    ) -> tuple[list[str], int]:
        """按可用 Token 截断证据文本。"""
        result: list[str] = []
        used = 0
        for text in texts:
            tokens = self.counter.count(text)
            if used + tokens <= available:
                result.append(text)
                used += tokens
            else:
                remaining = available - used
                if remaining > 20:
                    truncated = self._truncate_text(text, remaining)
                    result.append(truncated)
                    used += self.counter.count(truncated)
                break
        return result, used

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """截断单段文本到指定 Token 限制。"""
        # 粗略按字符数截断：token ≈ char_count / 3
        max_chars = max_tokens * 3
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "…"
