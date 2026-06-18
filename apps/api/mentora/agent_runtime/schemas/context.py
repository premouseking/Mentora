"""
上下文 Schema：AgentContext、ToolContext 和 ContextAllocation。

约定：
- AgentContext 由 ContextManager 组装后传入 Agent.run()
- ToolContext 由 Orchestrator 注入每次工具调用
- ContextAllocation 记录上下文空间分配结果

@module mentora/agent_runtime/schemas/context
"""

from pydantic import BaseModel, Field

from mentora.model_gateway.schemas import Message


class ContextAllocation(BaseModel):
    """上下文 Token 分配结果。"""
    system_tokens: int = 0
    user_query_tokens: int = 0
    history_tokens: int = 0
    evidence_tokens: int = 0
    total_tokens: int = 0
    within_budget: bool = False


class AgentContext(BaseModel):
    """Agent 运行时上下文。

    包含组装好的消息列表、系统提示词和上下文分配信息。
    """

    messages: list[Message] = Field(default_factory=list)
    system_prompt: str = ""
    allocation: ContextAllocation = Field(default_factory=ContextAllocation)


class ToolContext(BaseModel):
    """工具执行的上下文，由 Orchestrator 注入。"""
    task_id: str = Field(description="OrchestratorRun ID")
    agent_role: str = Field(description="当前 Agent 角色")
    run_id: str = Field(description="SubAgentRun ID")
    owner_id: str = Field(default="", description="用户 ID")
