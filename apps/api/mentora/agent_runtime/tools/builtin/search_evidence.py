"""
资料证据检索工具。

约定：
- 只读封装 mentora.retrieval.search，不暴露资料全文。
- 返回检索结果摘要（preview + score + evidence_id）。

@module mentora/agent_runtime/tools/builtin/search_evidence
"""

from __future__ import annotations

import json

from mentora.retrieval.search import search

from ..base import Tool, ToolContext
from ...contracts import ToolResult


class SearchEvidenceTool(Tool):
    @property
    def name(self) -> str:
        return "search_evidence"

    @property
    def description(self) -> str:
        return "在课程资料库中检索与查询相关的证据片段，返回带引用的预览文本。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询词，使用与用户问题相关的关键词。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的最大条数，默认 5。",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        }

    def run(self, arguments: dict, context: ToolContext) -> ToolResult:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return ToolResult(
                content=json.dumps({"error": "query 不能为空"}, ensure_ascii=False),
                is_error=True,
            )

        top_k = int(arguments.get("top_k", 5))
        top_k = max(1, min(top_k, 20))

        result_set = search(query=query, top_k=top_k)
        payload = result_set.to_dict()
        if context.scope_revision_id:
            payload["scope_revision_id"] = context.scope_revision_id

        return ToolResult(content=json.dumps(payload, ensure_ascii=False))
