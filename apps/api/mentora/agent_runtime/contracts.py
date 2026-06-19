"""
Agent 运行时契约类型。

约定：
- AgentMessage 是 agent 层对话历史的基本单元，可桥接为 model_gateway.ModelMessage。
- AgentEvent 预留统一事件协议，后续对接 SSE / WAL。

约束：
- 不得在此类型中写入 Token、预签名 URL 或私有资料正文。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
@module mentora/agent_runtime/contracts
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum

from mentora.model_gateway.contracts import QualityTier, TokenUsage, ToolCall


class AgentEventType(str, Enum):
    """Turn 级事件类型（借鉴 lightest ServerEvent，剥离厂商差异）。"""

    ROUND_START = "round_start"
    TOKEN_DELTA = "token_delta"
    TOOL_CALL_BEGIN = "tool_call_begin"
    TOOL_CALL_END = "tool_call_end"
    TURN_END = "turn_end"
    ERROR = "error"


@dataclass(frozen=True)
class AgentMessage:
    """Agent 对话历史中的单条消息。"""

    role: str  # system / user / assistant / tool
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果，回填到 history 前由 registry 格式化。"""

    content: str
    is_error: bool = False


@dataclass(frozen=True)
class AgentEvent:
    """对外可观察的 turn 事件。"""

    type: AgentEventType
    round_index: int = 0
    tool_name: str | None = None
    tool_call_id: str | None = None
    text: str = ""
    error: str | None = None


@dataclass(frozen=True)
class AgentConfig:
    """单次 Agent turn 的运行配置。"""

    task_type: str = "agent.turn"
    quality_tier: QualityTier = QualityTier.BALANCED
    max_iterations: int = 12
    max_output_tokens: int = 2048
    temperature: float = 0.2
    prompt_version: str = "agent-base-v3"
    token_budget: int = 32_000


@dataclass
class AgentResult:
    """Turn 结束后的聚合结果。"""

    text: str
    rounds: int
    finish_reason: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    messages: list[AgentMessage] = field(default_factory=list)


EventEmitter = Callable[[AgentEvent], None]
StreamEmitter = Iterator[AgentEvent]
