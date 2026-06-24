"""
课程作用域工具：提供课程信息查询，使 Agent 能感知当前课程的资料范围。

约定：
- source_version_ids 当前从 CourseCreationSession.extra 读取
- 后续 courses 模块补充正式 FK 后，切换查询逻辑，Tool 接口不变

@module mentora/agent_runtime/tools/course_tools
"""

from asgiref.sync import sync_to_async
from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class QueryCourseScopeTool(Tool):
    """查询课程作用域工具。

    返回课程目标、进度、已激活的资料版本列表。
    PlannerAgent 和 TutorAgent 在生成计划或回答前调用，
    拿到 source_version_ids 限定 retrieve_evidence 的检索范围。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        course_session_id = args.get("course_session_id", "")

        if not course_session_id:
            return ToolResult(
                tool_name="query_course_scope",
                success=False,
                error="缺少 course_session_id 参数",
            )

        try:
            from mentora.courses.models import CourseCreationSession

            session = await sync_to_async(
                CourseCreationSession.objects.get
            )(id=course_session_id)

            return ToolResult(
                tool_name="query_course_scope",
                success=True,
                result={
                    "course_session_id": str(session.id),
                    "goal": session.goal or "",
                    "level": session.level or "",
                    "pace": session.pace or "",
                    "school": session.school or "",
                    "status": session.status,
                    "source_version_ids": session.extra.get("source_version_ids", []),
                },
            )
        except CourseCreationSession.DoesNotExist:
            return ToolResult(
                tool_name="query_course_scope",
                success=False,
                error=f"课程会话不存在: {course_session_id}",
            )
        except Exception as e:
            return ToolResult(
                tool_name="query_course_scope",
                success=False,
                error=str(e),
            )
