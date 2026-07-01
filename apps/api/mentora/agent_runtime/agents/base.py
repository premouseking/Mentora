"""
Agent 抽象基类。

约定：
- Agent 是无状态纯函数，每次 run() 接收完整输入返回结构化输出
- 不 import 领域模型（Course、Topic 等）
- 不直接调用 LLM（通过 model_gateway）

约束：
- 子类必须实现 run() 方法
- system_prompt_ref 指向 PromptManager 中的模板名

@module mentora/agent_runtime/agents/base
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from mentora.agent_runtime.schemas.context import AgentContext
from mentora.agent_runtime.schemas.output import AgentOutput
from mentora.agent_runtime.tools.base import ToolDefinition


class AgentInput(BaseModel):
    """单次 Agent 调用的完整输入。"""
    task_id: str = Field(description="关联的 OrchestratorRun ID")
    user_message: str = Field(min_length=1, description="用户消息正文")
    context: AgentContext = Field(description="上下文（组装好的消息列表）")
    model_id: str | None = Field(default=None, description="Model override for this call.")
    tools: list[ToolDefinition] = Field(
        default_factory=list,
        description="本次可用的工具定义",
    )
    max_tool_rounds: int = Field(default=5, description="最大工具调用轮次")
    audit_sub_agent_run_id: str = Field(
        default="",
        description="RunManager 子 Agent 运行 ID，供 tool 审计持久化",
    )


class Agent(ABC):
    """无状态 Agent 基类。

    使用方式：
    ```python
    agent = TutorAgent(prompt_manager, tool_registry, model_gateway)
    output = await agent.run(agent_input)
    ```
    """

    role: str
    system_prompt_ref: str
    tool_names: set[str] = set()

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        """执行 Agent 推理。

        参数：
        - input: 完整的 Agent 输入（消息、工具、上下文）

        返回：结构化 AgentOutput
        """
        ...
