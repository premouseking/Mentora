"""
工具抽象与执行上下文。

约定：
- Tool 实现只能调用领域服务，禁止直接写领域表。
- ToolContext 携带非敏感的任务上下文（owner、课程版本快照等）。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
@module mentora/agent_runtime/tools/base
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from mentora.model_gateway.contracts import ToolSpec

from ..contracts import ToolResult


@dataclass
class ToolContext:
    """工具执行时可用的只读上下文。"""

    owner_id: str = ""
    course_id: str | None = None
    scope_revision_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class Tool(ABC):
    """Agent 可调用的领域工具。"""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """OpenAI function parameters JSON Schema。"""
        raise NotImplementedError

    def to_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    def run(self, arguments: dict, context: ToolContext) -> ToolResult:
        raise NotImplementedError
