"""
受控多轮 tool-loop 学习 Agent 运行时。

约定：
- ToolRegistry + ContextManager + PromptBuilder 组成通用 Agent 内核。
- 开放推理走 tool-loop；结构化业务流程仍由领域状态机负责。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
@module mentora/agent_runtime
"""

from .contracts import AgentConfig, AgentEvent, AgentResult
from .session import AgentSession

__all__ = ["AgentConfig", "AgentEvent", "AgentResult", "AgentSession"]

