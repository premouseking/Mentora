"""
PlannerAgent：基于用户目标和资料生成学习计划。

约定：
- 使用 retrieve_evidence 工具检索资料
- 工具循环委托 turn_loop 统一实现

@module mentora/agent_runtime/agents/planner
"""

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.agents.turn_loop import run_tool_loop
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.output import AgentOutput
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway


class PlannerAgent(Agent):
    """学习计划生成 Agent。"""

    role = "planner"
    system_prompt_ref = "planner"
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
        )
