"""
学习计划工具：操作学习计划与任务。

约定：
- 当前 learning 模块尚未实现，Tool 返回清晰的未就绪错误
- 后续填入真实逻辑时 Tool 接口不变

归属 Agent: planner
@module mentora/agent_runtime/tools/learning_tools
"""

from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class CreateLearningPlanTool(Tool):
    """创建学习计划工具。

    接收 PlannerAgent 生成的结构化计划，持久化到 learning 模块。
    当前为 placeholder——learning 模块未实现。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(
            tool_name="create_learning_plan",
            success=False,
            error="learning 模块尚未实现",
        )
