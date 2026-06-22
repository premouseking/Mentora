"""
TutorAgent：基于资料的教学问答 Agent。

约定：
- 使用 retrieve_evidence 工具检索资料
- 工具循环委托 turn_loop 统一实现

@module mentora/agent_runtime/agents/tutor
"""

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.agents.turn_loop import run_tool_loop, run_tool_loop_stream
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.output import AgentOutput, Citation
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.schemas import ChatResponse


class TutorAgent(Agent):
    """教学问答 Agent。"""

    role = "tutor"
    system_prompt_ref = "tutor"
    tool_names: set[str] = {"retrieve_evidence"}

    def __init__(
        self,
        prompt_manager: PromptManager,
        tool_registry: ToolRegistry,
        model_gateway: ModelGateway,
    ):
        self._prompts = prompt_manager
        self._registry = tool_registry
        self._gateway = model_gateway

    async def run(self, input: AgentInput) -> AgentOutput:
        return await run_tool_loop(
            agent_role=self.role,
            agent_input=input,
            registry=self._registry,
            gateway=self._gateway,
            extract_citations=self._extract_citations,
        )

    async def run_stream(
        self,
        input: AgentInput,
        emitter=None,
    ) -> AgentOutput:
        return await run_tool_loop_stream(
            agent_role=self.role,
            agent_input=input,
            registry=self._registry,
            gateway=self._gateway,
            emitter=emitter,
            extract_citations=self._extract_citations,
        )

    def _extract_citations(self, resp: ChatResponse) -> list[Citation]:
        """从响应中提取证据引用（后续通过结构化输出完善）。"""
        return []
