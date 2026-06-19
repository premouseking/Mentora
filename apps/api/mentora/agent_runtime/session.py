"""
Agent 会话门面：组合 registry、context、config 并驱动 run_turn。

@module mentora/agent_runtime/session
"""

from __future__ import annotations

from collections.abc import Iterator

from mentora.model_gateway.gateway import ModelGateway

from .context import ContextManager
from .contracts import AgentConfig, AgentEvent, AgentResult, EventEmitter
from .loop import run_turn, run_turn_stream
from .tools.base import Tool, ToolContext
from .tools.registry import ToolRegistry


class AgentSession:
    def __init__(
        self,
        *,
        config: AgentConfig | None = None,
        tools: list[Tool] | None = None,
        tool_context: ToolContext | None = None,
        dynamic_context: str = "",
        gateway: ModelGateway | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.registry = ToolRegistry(tools)
        self.context = ContextManager(token_budget=self.config.token_budget)
        self.tool_context = tool_context or ToolContext()
        self.dynamic_context = dynamic_context
        self._gateway = gateway

    def run(
        self,
        user_input: str,
        *,
        emit: EventEmitter | None = None,
        stream: bool = False,
    ) -> AgentResult:
        return run_turn(
            user_input=user_input,
            context=self.context,
            registry=self.registry,
            config=self.config,
            tool_context=self.tool_context,
            dynamic_context=self.dynamic_context,
            gateway=self._gateway,
            emit=emit,
            stream=stream,
        )

    def run_stream(self, user_input: str) -> Iterator[AgentEvent]:
        """流式执行 turn，逐 AgentEvent yield（含 TOKEN_DELTA）。"""
        return run_turn_stream(
            user_input=user_input,
            context=self.context,
            registry=self.registry,
            config=self.config,
            tool_context=self.tool_context,
            dynamic_context=self.dynamic_context,
            gateway=self._gateway,
        )
