"""
知识检索工具：retrieve_evidence 实现。

约定：
- 调用 mentora.retrieval.search.search() 执行混合检索
- 返回证据片段、页码和坐标信息

约束：
- 只读工具，无需用户确认
- 结果截断到 top_k 条

@module mentora/agent_runtime/tools/knowledge_tools
"""

import json
from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolResult


class RetrieveEvidenceTool(Tool):
    """检索资料证据工具。

    调用 mentora.retrieval.search.search() 执行混合检索（FTS + Trgm + RRF）。
    """

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        query = args.get("query", "")
        top_k = args.get("top_k", 5)

        if not query.strip():
            return ToolResult(
                tool_name="retrieve_evidence",
                success=False,
                error="查询不能为空",
            )

        # 作用域：优先 args，次之 metadata / course_id 自动解析
        source_version_ids = args.get("source_version_ids")
        if not source_version_ids:
            allowed = ctx.metadata.get("allowed_source_version_ids")
            if isinstance(allowed, list) and allowed:
                source_version_ids = allowed
            elif ctx.course_id:
                from mentora.courses.services import get_course_scope

                source_version_ids = get_course_scope(ctx.course_id)

        try:
            from mentora.retrieval.search import async_search

            result_set = await async_search(
                query=query, top_k=top_k, source_version_ids=source_version_ids,
            )
            results = [r.to_dict() for r in result_set.results]

            return ToolResult(
                tool_name="retrieve_evidence",
                success=True,
                result={
                    "query": query,
                    "total_candidates": result_set.total_candidates,
                    "results": results,
                    "elapsed_ms": result_set.elapsed_ms,
                },
                duration_ms=result_set.elapsed_ms,
            )
        except Exception as e:
            return ToolResult(
                tool_name="retrieve_evidence",
                success=False,
                error=f"检索失败: {e}",
            )
