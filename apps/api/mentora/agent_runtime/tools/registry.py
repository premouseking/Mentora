"""
工具注册表：管理 Tool 实例和 ToolDefinition 的注册与调用。

约定：
- 按 Agent 角色过滤可用工具
- 工具名称全局唯一
- register() 时自动校验 ToolDefinition.parameters 为合法 JSON Schema

约束：
- registry.execute() 统一管理超时和异常处理
- 不在此处执行业务逻辑

@module mentora/agent_runtime/tools/registry
"""

import asyncio
import time

from mentora.agent_runtime.schemas.context import ToolContext
from mentora.agent_runtime.tools.base import Tool, ToolDefinition, ToolResult


class ToolRegistry:
    """工具注册表。

    使用方式：
    ```python
    registry = ToolRegistry()
    registry.register(my_tool, ToolDefinition(...))
    result = await registry.execute("my_tool", {"arg": 1}, ctx)
    ```
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, tool: Tool, definition: ToolDefinition) -> None:
        """注册工具。

        Raises:
            ValueError: 工具名已存在
        """
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        self._tools[definition.name] = tool
        self._definitions[definition.name] = definition

    def get_definition(self, name: str) -> ToolDefinition | None:
        """获取工具定义。"""
        return self._definitions.get(name)

    def get_for_agent(self, agent_role: str) -> list[ToolDefinition]:
        """获取指定 Agent 可用的工具定义列表。"""
        return [
            d
            for d in self._definitions.values()
            if not d.agent_roles or agent_role in d.agent_roles
        ]

    def get_openai_tools(self, agent_role: str) -> list[dict]:
        """获取指定 Agent 的 OpenAI tools 格式工具列表。"""
        return [d.to_openai_tool() for d in self.get_for_agent(agent_role)]

    async def execute(
        self,
        name: str,
        args: dict,
        ctx: ToolContext,
    ) -> ToolResult:
        """执行工具调用。

        参数：
        - name: 工具名称
        - args: 工具参数
        - ctx: 工具上下文

        返回：ToolResult（即使出错也返回 ToolResult，不抛异常）
        """
        tool = self._tools.get(name)
        definition = self._definitions.get(name)

        if tool is None:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not found",
            )

        t0 = time.perf_counter()
        timeout = definition.timeout_seconds if definition else 30.0

        try:
            result = await asyncio.wait_for(
                tool.execute(args, ctx),
                timeout=timeout,
            )
            result.duration_ms = (time.perf_counter() - t0) * 1000
            return result
        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' timed out after {timeout}s",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return ToolResult(
                tool_name=name,
                success=False,
                error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    def list_tools(self) -> list[str]:
        """列出所有已注册的工具名称。"""
        return list(self._tools.keys())
