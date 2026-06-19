"""
工具注册表：向模型暴露 ToolSpec，并分发 tool_calls。

约束：
- 未知工具名返回结构化错误，仍回填 history 以触发模型自我修正。

@module mentora/agent_runtime/tools/registry
"""

from __future__ import annotations

import json

from mentora.model_gateway.contracts import ToolCall, ToolSpec

from ..contracts import ToolResult
from .base import Tool, ToolContext


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.to_spec() for tool in self._tools.values())

    def tool_names(self) -> tuple[str, ...]:
        return tuple(self._tools.keys())

    def dispatch(self, call: ToolCall, context: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                content=json.dumps(
                    {"error": f"未知工具: {call.name}"},
                    ensure_ascii=False,
                ),
                is_error=True,
            )

        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            return ToolResult(
                content=json.dumps(
                    {"error": f"工具参数不是合法 JSON: {call.name}"},
                    ensure_ascii=False,
                ),
                is_error=True,
            )

        if not isinstance(arguments, dict):
            return ToolResult(
                content=json.dumps(
                    {"error": f"工具参数必须是 JSON 对象: {call.name}"},
                    ensure_ascii=False,
                ),
                is_error=True,
            )

        try:
            return tool.run(arguments, context)
        except Exception as exc:  # noqa: BLE001 — 工具边界须兜底，避免打断 turn
            return ToolResult(
                content=json.dumps(
                    {"error": f"工具执行失败: {type(exc).__name__}"},
                    ensure_ascii=False,
                ),
                is_error=True,
            )
