"""
输出 Schema：AgentOutput、OrchestratorResult 等。

约定：
- AgentOutput 是单个 Agent 运行的结果
- OrchestratorResult 是编排器的最终结果
- Citation 包含证据引用信息

@module mentora/agent_runtime/schemas/output
"""

from uuid import UUID

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token 用量统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Citation(BaseModel):
    """证据引用，关联到 EvidenceUnit。"""
    evidence_id: str = Field(description="EvidenceUnit UUID")
    content_preview: str = Field(default="", description="引用内容预览")
    page_number: int | None = Field(default=None, description="所在页码")


class ToolInvocationRecord(BaseModel):
    """工具调用记录（Agent 输出中嵌入）。"""
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    success: bool = False
    duration_ms: float = 0.0


class AgentOutput(BaseModel):
    """单个 Agent 运行的结构化输出。"""
    agent_role: str = Field(description="Agent 角色")
    task_id: str = Field(description="关联的 OrchestratorRun ID")
    final_message: str = Field(default="", description="最终回复文本")
    citations: list[Citation] = Field(default_factory=list)
    tool_calls_made: list[ToolInvocationRecord] = Field(default_factory=list)
    finish_reason: str = Field(
        default="completed",
        description="完成原因：completed | max_rounds | error",
    )
    usage: TokenUsage = Field(default_factory=TokenUsage)
    sub_agent_run_id: str | None = Field(
        default=None,
        description="关联的 SubAgentRun ID",
    )


class OrchestratorResult(BaseModel):
    """编排器最终结果。"""
    task_id: str
    mode: str
    status: str = Field(description="completed | failed | cancelled")
    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    final_output: AgentOutput | None = None
    total_duration_ms: float = 0.0
    total_tool_calls: int = 0
    total_usage: TokenUsage = Field(default_factory=TokenUsage)
    error_code: str = ""
    error_message: str = ""
