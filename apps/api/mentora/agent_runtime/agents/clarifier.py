"""
ClarifierAgent：当用户意图模糊时提出澄清问题。

约定：
- 纯文本交互，不使用工具
- 不检索资料（不属于知识问答范畴）

@module mentora/agent_runtime/agents/clarifier
"""

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.output import AgentOutput, TokenUsage
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway


class ClarifierAgent(Agent):
    """学习意图澄清 Agent。

    职责：
    - 当用户表述模糊时提出 2-3 个澄清问题
    - 帮助用户明确学习目标、已有基础、时间约束
    - 不需要任何工具，纯文本交互
    """

    role = "clarifier"
    system_prompt_ref = "clarifier"
    tool_names: set[str] = set()  # 不使用工具

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
        """执行意图澄清。

        ClarifierAgent 只做一轮对话，不循环调用工具。
        """
        # 直接发起单轮对话，不带 tools
        resp = await self._gateway.chat(
            task_type=self.role,
            messages=list(input.context.messages),
            tools=None,
        )

        usage = TokenUsage()
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
            )

        return AgentOutput(
            agent_role=self.role,
            task_id=input.task_id,
            final_message=resp.content or "",
            citations=[],
            tool_calls_made=[],
            finish_reason="completed",
            usage=usage,
        )
