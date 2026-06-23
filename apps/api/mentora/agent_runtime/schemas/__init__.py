"""
Agent Runtime Schema 层：所有跨模块 Pydantic DTO。

约定：
- 纯 Pydantic 模型，不依赖 Django ORM
- 所有 DTO 可 JSON 序列化（model_dump(mode="json")）
- 不在此处定义业务逻辑

@module mentora/agent_runtime/schemas
"""

from mentora.agent_runtime.schemas.context import AgentContext, ContextAllocation, ToolContext
from mentora.agent_runtime.schemas.output import (
    AgentOutput,
    Citation,
    OrchestratorResult,
    TokenUsage,
)
from mentora.agent_runtime.schemas.task import (
    BudgetConfig,
    OrchestratorTask,
    PipelineStep,
)

__all__ = [
    "AgentContext",
    "AgentOutput",
    "BudgetConfig",
    "Citation",
    "ContextAllocation",
    "OrchestratorResult",
    "OrchestratorTask",
    "PipelineStep",
    "TokenUsage",
    "ToolContext",
]
