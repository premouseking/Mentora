"""
课程作用域工具：提供课程信息查询，使 Agent 能感知当前课程的资料范围。

约定：
- 优先 course_id（正式课程，读 Course → ProfileRevision → ScopeBinding）
- 回退 course_session_id（建课未确认，读 Session.extra）

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
        course_id = args.get("course_id") or ctx.course_id
        course_session_id = args.get("course_session_id", "")

        if not course_id and not course_session_id:
            return ToolResult(
                tool_name="query_course_scope",
                success=False,
                error="缺少 course_id 或 course_session_id 参数",
            )

        try:
            if course_id:
                return await self._query_course(course_id)
            return await self._query_session(course_session_id)
        except Exception as e:
            return ToolResult(
                tool_name="query_course_scope",
                success=False,
                error=str(e),
            )

    async def _query_course(self, course_id: str) -> ToolResult:
        from mentora.courses.models import Course, CourseProfileRevision
        from mentora.courses.services import get_course_scope

        course = await sync_to_async(Course.objects.get)(id=course_id)
        profile = None
        if course.active_profile_revision_id:
            profile = await sync_to_async(
                CourseProfileRevision.objects.get
            )(id=course.active_profile_revision_id)

        source_version_ids = get_course_scope(course_id) or []

        return ToolResult(
            tool_name="query_course_scope",
            success=True,
            result={
                "course_id": str(course.id),
                "goal": profile.goal if profile else "",
                "level": profile.level if profile else "",
                "pace": profile.pace if profile else "",
                "school": profile.school if profile else "",
                "status": profile.status if profile else "",
                "source_version_ids": source_version_ids,
            },
        )

    async def _query_session(self, session_id: str) -> ToolResult:
        from mentora.courses.models import CourseCreationSession

        session = await sync_to_async(
            CourseCreationSession.objects.get
        )(id=session_id)

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
