"""
评估工具：题目生成与管理。

约定：
- AssessorAgent 生成题目内容（通过 LLM），工具负责持久化
- create_item / create_session / submit_attempt 调用 assessment.services

@module mentora/agent_runtime/tools/assessment_tools
"""

from asgiref.sync import sync_to_async
from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class GenerateItemTool(Tool):
    """生成评估题目工具。

    AssessorAgent 通过 LLM 推理生成题目内容后，调用本工具持久化到 assessment 模块。
    同时创建测验会话并关联题目，学生可立即开始作答。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        items = args.get("items") or args.get("questions")

        if not items:
            return ToolResult(
                tool_name="generate_item",
                success=False,
                error="缺少 items 参数",
            )
        if not isinstance(items, list) or len(items) == 0:
            return ToolResult(
                tool_name="generate_item",
                success=False,
                error="items 必须为非空数组",
            )

        course_session_id = args.get("course_session_id", "")
        if not course_session_id:
            return ToolResult(
                tool_name="generate_item",
                success=False,
                error="缺少 course_session_id 参数",
            )

        try:
            from mentora.assessment.services import create_item, create_session

            created_ids = []
            for item_data in items:
                result = await sync_to_async(create_item)(
                    course_session_id=course_session_id,
                    question_type=item_data.get("question_type", "single_choice"),
                    question_text=item_data["question_text"],
                    correct_answer=item_data["correct_answer"],
                    topic_id=item_data.get("topic_id", ""),
                    difficulty=item_data.get("difficulty", 3),
                    options_json=item_data.get("options_json"),
                    explanation=item_data.get("explanation", ""),
                    source_evidence_ids=item_data.get("source_evidence_ids", []),
                )
                created_ids.append(result["item_id"])

            # 创建测验会话
            session_result = await sync_to_async(create_session)(
                course_session_id=course_session_id,
                item_ids=created_ids,
                unit_id=args.get("unit_id", ""),
            )

            return ToolResult(
                tool_name="generate_item",
                success=True,
                result={
                    "session_id": session_result["session_id"],
                    "item_ids": created_ids,
                    "item_count": len(created_ids),
                },
            )
        except Exception as e:
            return ToolResult(
                tool_name="generate_item",
                success=False,
                error=str(e),
            )


class SubmitAnswerTool(Tool):
    """提交作答工具。

    记录学生单题作答并自动判分（对比题干 correct_answer）。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        session_id = args.get("session_id", "")
        item_id = args.get("item_id", "")
        user_answer = args.get("user_answer", "")

        if not session_id or not item_id:
            return ToolResult(
                tool_name="submit_answer",
                success=False,
                error="缺少 session_id 或 item_id 参数",
            )

        try:
            from mentora.assessment.services import submit_attempt

            result = await sync_to_async(submit_attempt)(
                session_id=session_id,
                item_id=item_id,
                user_answer=user_answer,
                duration_seconds=args.get("duration_seconds"),
            )

            return ToolResult(
                tool_name="submit_answer",
                success=True,
                result=result,
            )
        except Exception as e:
            return ToolResult(
                tool_name="submit_answer",
                success=False,
                error=str(e),
            )
