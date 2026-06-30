"""
模型网关 Pydantic DTO：请求、响应、工具调用和 Provider 响应。

约定：
- Message 的 role 严格限定为 system/user/assistant/tool
- ToolCall 遵循 OpenAI Function Calling 协议
- TokenUsage 记录每次调用的 token 消耗

约束：
- 所有 DTO 使用 Pydantic v2 风格（model_validate, Field）
- 不在此处定义业务 Schema（归 agent_runtime/schemas/）

@module mentora/model_gateway/schemas
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    """LLM 请求调用的函数。"""
    name: str = Field(description="函数名称")
    arguments: str = Field(description="JSON 编码的函数参数")


class ToolCall(BaseModel):
    """单次工具调用请求（来自 LLM 响应）。"""
    id: str = Field(description="工具调用唯一 ID")
    type: Literal["function"] = "function"
    function: FunctionCall


class Message(BaseModel):
    """对话消息。

    约束：role 只能是 system / user / assistant / tool。
    """
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = Field(default=None, description="tool 消息的工具名称")
    tool_call_id: str | None = Field(default=None, description="关联的 tool_call ID")
    tool_calls: list[ToolCall] | None = Field(default=None, description="assistant 消息的 tool_calls")


class TokenUsage(BaseModel):
    """Token 用量统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProviderResponse(BaseModel):
    """模型提供方返回的原始响应。"""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"
    usage: TokenUsage | None = None
    model: str = ""


class ChatRequest(BaseModel):
    """网关聊天请求。"""
    task_type: str = Field(description="任务类型，用于路由和审计")
    messages: list[Message]
    tools: list[dict[str, Any]] | None = None
    structured_output_schema_name: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class ChatResponse(BaseModel):
    """网关聊天响应。"""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"
    usage: TokenUsage | None = None
    model: str = ""
    parsed_output: dict[str, Any] | None = None
