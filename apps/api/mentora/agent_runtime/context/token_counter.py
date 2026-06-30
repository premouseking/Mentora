"""
Token 计数器：粗略 Token 估算。

约定：
- 使用 len(text) // 4 近似算法
- 不引入 tiktoken 等外部依赖
- 误差在 ±20% 内可接受

@module mentora/agent_runtime/context/token_counter
"""

from mentora.model_gateway.schemas import Message


class TokenCounter:
    """粗略 Token 计数器。

    约束：
    - 中文文本按字符数/2 估算（中文字符通常 1-2 token）
    - 英文文本按字符数/4 估算
    - 简单算法 O(n) 扫描，适合毫秒级响应
    """

    def count(self, text: str) -> int:
        """估算单段文本的 Token 数。"""
        if not text:
            return 0
        # 粗略估算：平均字符/token ≈ 3（混合中英文）
        return max(1, len(text) // 3)

    def count_messages(self, messages: list[Message]) -> int:
        """估算消息列表的总 Token 数。"""
        total = 0
        for msg in messages:
            if msg.content:
                total += self.count(msg.content)
            # 函数调用参数也计入
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total += self.count(tc.function.arguments)
                    total += self.count(tc.function.name)
        return total

    def count_system_prompt(self, prompt: str) -> int:
        """估算系统提示词 Token 数。"""
        return self.count(prompt)
