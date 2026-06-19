"""
模型网关的厂商无关契约类型。

约定：
- 这些类型是领域服务与网关之间的唯一交换协议，不含任何厂商 SDK 类型。
- ModelRequest 声明「想要什么」（任务、质量档、预算、结构化 schema），
  不声明「用哪个模型」；具体选型由网关路由决定。
- ModelResponse 同时记录 requested 与 actual，并保留每次物理调用的 ModelAttempt，
  失败 Attempt 也不丢弃，用于审计与成本对账。

约束：
- structured_output_schema 为 Pydantic 模型类时，网关会强制 JSON 模式并在
  返回前完成校验；校验失败不进入领域回调。
- 任何字段都不得写入 Token、预签名 URL 或私有资料正文等敏感数据。

@see docs/architecture/technical-solution.md §模型网关
@module mentora/model_gateway/contracts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class QualityTier(str, Enum):
    """质量档：仅表达业务对质量/成本的诉求，不绑定具体模型。"""

    FAST = "fast"
    BALANCED = "balanced"
    PREMIUM = "premium"


class Capability(str, Enum):
    """模型能力声明，供路由匹配；当前仅作为审计与未来扩展位。"""

    TEXT = "text"
    JSON = "json"
    LONG_CONTEXT = "long_context"
    VISION = "vision"


class AttemptStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True)
class ToolCall:
    """模型返回的单次工具调用。"""

    id: str
    name: str
    arguments: str  # JSON 字符串


@dataclass(frozen=True)
class ToolSpec:
    """注册给模型的工具描述（OpenAI function 形态）。"""

    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass(frozen=True)
class ModelMessage:
    """单条对话消息。content 仅承载非敏感的任务文本。"""

    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None  # role=tool 时必填


@dataclass(frozen=True)
class ModelRequest:
    """一次逻辑任务的请求。由领域服务构造，网关消费。"""

    task_type: str
    messages: list[ModelMessage]
    quality_tier: QualityTier = QualityTier.BALANCED
    required_capabilities: tuple[Capability, ...] = ()
    # 结构化输出 schema：传入则强制 JSON 模式并在返回前校验。
    structured_output_schema: type[BaseModel] | None = None
    latency_budget_ms: int | None = None
    cost_budget_usd: float | None = None
    max_output_tokens: int = 1024
    temperature: float = 0.2
    tools: tuple[ToolSpec, ...] = ()
    tool_choice: str = "auto"
    # 透传给审计的非敏感元数据（如 evidence_snapshot_id、prompt_version）。
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelAttempt:
    """一次物理调用记录。成功与失败都保留，供审计与成本对账。"""

    provider: str
    model: str
    status: AttemptStatus
    latency_ms: int
    usage: TokenUsage = TokenUsage()
    # 失败原因摘要，已剥离敏感内容，仅保留可审计的错误类别与信息。
    error: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    """网关返回的候选结果。业务校验由领域服务在此之后执行。"""

    text: str
    requested_model: str
    actual_model: str
    provider: str
    finish_reason: str
    usage: TokenUsage
    attempts: list[ModelAttempt]
    # 当请求带 structured_output_schema 时，已校验通过的 Pydantic 实例。
    structured: BaseModel | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class StreamEventType(str, Enum):
    """归一化流事件类型。"""

    DELTA = "delta"
    DONE = "done"


@dataclass(frozen=True)
class StreamEvent:
    """
    网关对外的统一流事件。

    约定：
    - DELTA：增量文本，text 为本次增量片段，response 为空。
    - DONE：流结束，response 为聚合后的完整 ModelResponse（含 usage 与 attempts）。
    """

    type: StreamEventType
    text: str = ""
    response: ModelResponse | None = None
