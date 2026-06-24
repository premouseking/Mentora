"""
学习计划工具：创建与查询学习计划。

约定：
- 调 learning.services 持久化 PlannerAgent 输出的计划 JSON
- course_session_id 优先从 args 取，次之从 ToolContext 推断
- 只读工具无需确认，写操作（create_plan）当前无人机交互确认流程，暂允许直接写入

@module mentora/agent_runtime/tools/learning_tools
"""

from asgiref.sync import sync_to_async
from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class CreateLearningPlanTool(Tool):
    """创建学习计划工具。

    接收 PlannerAgent 生成的结构化计划 JSON，持久化到 learning 模块。
    自动创建 Plan → Revision → Phase → Unit → TaskTemplate 全量结构。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        plan_snapshot = args.get("plan_snapshot") or args.get("plan")

        if not plan_snapshot:
            return ToolResult(
                tool_name="create_learning_plan",
                success=False,
                error="缺少 plan_snapshot 参数",
            )
        if not isinstance(plan_snapshot, dict):
            return ToolResult(
                tool_name="create_learning_plan",
                success=False,
                error="plan_snapshot 必须为 JSON 对象",
            )

        course_session_id = args.get("course_session_id", "")
        if not course_session_id:
            return ToolResult(
                tool_name="create_learning_plan",
                success=False,
                error="缺少 course_session_id 参数",
            )

        try:
            from mentora.learning.services import create_plan_revision

            result = await sync_to_async(create_plan_revision)(
                course_session_id=course_session_id,
                plan_snapshot=plan_snapshot,
                profile_revision_id=args.get("profile_revision_id", ""),
                knowledge_scope_revision_id=args.get("knowledge_scope_revision_id", ""),
            )

            return ToolResult(
                tool_name="create_learning_plan",
                success=True,
                result=result,
            )
        except Exception as e:
            return ToolResult(
                tool_name="create_learning_plan",
                success=False,
                error=str(e),
            )
