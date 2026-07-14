"""
评估工具：题目生成与管理。

@module mentora/agent_runtime/tools/assessment_tools
"""

from asgiref.sync import sync_to_async

from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult
from mentora.assessment.services.quiz_item_normalization import normalize_raw_items


class GenerateItemTool(Tool):
    """生成评估题目工具。"""

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

        metadata = ctx.metadata or {}
        allowed_evidence_ids = {
            str(eid).strip()
            for eid in (metadata.get("allowed_evidence_ids") or [])
            if str(eid).strip()
        }
        fallback_evidence_ids = [
            str(eid).strip()
            for eid in (metadata.get("fallback_evidence_ids") or [])
            if str(eid).strip()
        ]
        unit_id = str(args.get("unit_id") or metadata.get("unit_id") or "").strip()
        evidence_context = str(metadata.get("evidence_context") or "")

        try:
            from mentora.assessment.services.quiz_generation import persist_normalized_items

            normalized, skipped = normalize_raw_items(
                items,
                allowed_evidence_ids=allowed_evidence_ids,
                fallback_evidence_ids=fallback_evidence_ids,
            )
            if not normalized:
                return ToolResult(
                    tool_name="generate_item",
                    success=False,
                    error="题目格式无效",
                    result={"skipped": skipped},
                )

            session_id, persist_skipped = await persist_normalized_items(
                course_session_id=course_session_id,
                normalized_items=normalized,
                unit_id=unit_id,
                run_batch_validation=bool(evidence_context),
                evidence_context=evidence_context,
            )
            skipped.extend(persist_skipped)

            if not session_id:
                return ToolResult(
                    tool_name="generate_item",
                    success=False,
                    error="没有通过质量评估的题目",
                    result={"skipped": skipped},
                )

            return ToolResult(
                tool_name="generate_item",
                success=True,
                result={
                    "session_id": session_id,
                    "item_count": len(normalized) - len(persist_skipped),
                    "skipped": skipped,
                },
            )
        except Exception as e:
            return ToolResult(
                tool_name="generate_item",
                success=False,
                error=str(e),
            )


class SubmitAnswerTool(Tool):
    """提交作答工具。"""

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
