"""
编排任务 Schema：OrchestratorTask、PipelineStep 和预算配置。

约定：
- OrchestratorTask 是 workflow_runtime / API 与 Agent Runtime 之间的契约
- PipelineStep 用 Python 数据类定义，不存数据库
- BudgetConfig 控制上下文窗口预算上限

@module mentora/agent_runtime/schemas/task
"""

from pydantic import BaseModel, Field

from mentora.agent_runtime.schemas.output import TokenUsage
from mentora.model_gateway.schemas import Message


class BudgetConfig(BaseModel):
    """上下文窗口预算配置。"""
    max_tokens: int = Field(default=8000, description="总 Token 硬上限")
    system_reserved: int = Field(default=1500, description="系统提示词预留 Token")
    output_reserved: int = Field(default=1500, description="模型输出预留 Token")

    @property
    def available_for_messages(self) -> int:
        """可用于消息上下文的 Token 数。"""
        return max(0, self.max_tokens - self.system_reserved - self.output_reserved)


class PipelineStep(BaseModel):
    """Pipeline 模式中的一个执行步骤。

    约定：
    - agent_role 指定使用哪个 Agent
    - input_from 指向前一步骤的 output_key
    - output_key 为当前步骤输出的键名
    """

    agent_role: str = Field(description="Agent 角色标识")
    task_instruction: str = Field(description="本步骤的任务指令")
    input_from: str | None = Field(
        default=None,
        description="从哪个步骤的 output_key 取值作为输入",
    )
    output_key: str = Field(description="当前步骤的输出键名，供后续引用")
    max_tool_rounds: int = Field(default=5, description="本步骤最大工具调用轮次")


class OrchestratorTask(BaseModel):
    """编排任务：来自 workflow_runtime 或 API。

    约定：
    - mode="single" 时只用 agent_role 路由
    - mode="pipeline" 时按 pipeline_steps 顺序执行
    - history_messages 为历史对话消息（旧→新）
    """

    id: str = Field(description="任务唯一 ID")
    mode: str = Field(default="single", description="调度模式：single | pipeline")
    agent_role: str = Field(default="", description="目标 Agent 角色（pipeline 模式可为空）")
    user_message: str = Field(default="", description="用户消息正文（pipeline 模式可为空）")
    context_sources: list[str] = Field(
        default_factory=list,
        description="上下文资料版本 ID 列表",
    )
    history_messages: list[Message] = Field(
        default_factory=list,
        description="历史对话消息",
    )
    max_tool_rounds: int = Field(default=5, description="最大工具调用轮次")
    model_id: str | None = Field(
        default=None,
        description="Model override for this task.",
    )
    budget_config: BudgetConfig = Field(default_factory=BudgetConfig)
    pipeline_steps: list[PipelineStep] | None = Field(
        default=None,
        description="Pipeline 模式步骤定义",
    )
    usage: TokenUsage | None = Field(
        default=None,
        description="累计 Token 用量（运行结束后回填）",
    )
    tool_metadata: dict = Field(
        default_factory=dict,
        description="注入 ToolContext.metadata 的任务级元数据",
    )
