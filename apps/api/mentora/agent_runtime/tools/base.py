"""
工具基类：ToolDefinition、Tool 抽象和 ToolResult。

约定：
- Tool 是无状态的可调用对象，通过 execute() 执行
- ToolDefinition 提供元数据，用于生成 Function Calling 的 tools 参数
- ToolContext 从 schemas/context.py 导入，由 Orchestrator 注入

约束：
- Tool.execute() 不直接写领域数据库，通过领域服务间接操作
- timeout_seconds 超时由注册表统一管理

@module mentora/agent_runtime/tools/base
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from mentora.agent_runtime.schemas.context import ToolContext


class ToolResult(BaseModel):
    """工具执行结果。"""
    tool_name: str = Field(description="工具名称")
    success: bool = Field(default=True, description="是否执行成功")
    result: Any = Field(default=None, description="结构化结果")
    error: str | None = Field(default=None, description="错误信息")
    artifact_ref: str | None = Field(
        default=None,
        description="结果过大时写入 Artifact 的对象存储键",
    )
    duration_ms: float = Field(default=0.0, description="执行耗时（毫秒）")


@dataclass
class ToolDefinition:
    """工具元数据，用于生成 Function Calling tools 参数和注册。

    约定：
    - parameters 为 JSON Schema dict
    - agent_roles 控制哪些 Agent 可以使用此工具
    """

    name: str
    description: str
    parameters: dict
    agent_roles: set[str] = field(default_factory=set)
    requires_confirmation: bool = False
    timeout_seconds: float = 30.0

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI Function Calling tools 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Tool(ABC):
    """工具抽象基类。

    约束：
    - 子类必须实现 execute()
    - 不持有领域模型引用，通过 execute() 间接调用领域服务
    """

    @abstractmethod
    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        """执行工具调用。

        参数：
        - args: 工具参数（从 LLM tool_calls.function.arguments 解析）
        - ctx: 工具上下文（task_id, agent_role, run_id）

        返回：结构化 ToolResult
        """
        ...
