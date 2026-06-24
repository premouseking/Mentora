"""
评估工具：题目生成与评分。

约定：
- 当前 assessment 模块尚未实现，Tool 返回清晰的未就绪错误
- 后续填入真实逻辑时 Tool 接口不变

归属 Agent: assessor
@module mentora/agent_runtime/tools/assessment_tools
"""

from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class GenerateItemTool(Tool):
    """生成评估题目工具。

    接收 AssessorAgent 指定的主题、难度、题型，调用 assessment 模块出题。
    当前为 placeholder——assessment 模块未实现。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(
            tool_name="generate_item",
            success=False,
            error="assessment 模块尚未实现",
        )
