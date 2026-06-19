"""
PlannerAgent：基于用户目标和资料生成学习计划。

约定：
- 使用 retrieve_evidence 工具检索资料
- 通过 model_gateway 调用 LLM
- 输出结构化学习计划

@module mentora/agent_runtime/agents/planner
"""

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.output import AgentOutput, Citation, TokenUsage, ToolInvocationRecord
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.schemas import ChatResponse, Message, ToolCall


class PlannerAgent(Agent):
    """学习计划生成 Agent。

    职责：
    - 分析用户学习目标和已有资料
    - 检索相关资料确认可行性
    - 生成分阶段学习计划
    """

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
        """执行学习计划生成。"""
        total_usage = TokenUsage()
        tool_records: list[ToolInvocationRecord] = []
        chat_messages = list(input.context.messages)

        tools = self._registry.get_openai_tools(self.role)

        for round_num in range(input.max_tool_rounds):
            resp = await self._gateway.chat(
                task_type=self.role,
                messages=chat_messages,
                tools=tools,
            )

            if resp.usage:
                total_usage.prompt_tokens += resp.usage.prompt_tokens
                total_usage.completion_tokens += resp.usage.completion_tokens
                total_usage.total_tokens += resp.usage.total_tokens

            # 没有工具调用 → 最终回复（学习计划）
            if not resp.tool_calls:
                return AgentOutput(
                    agent_role=self.role,
                    task_id=input.task_id,
                    final_message=resp.content or "",
                    citations=self._extract_citations(resp),
                    tool_calls_made=tool_records,
                    finish_reason="completed",
                    usage=total_usage,
                )

            # 处理工具调用
            assistant_msg = Message(
                role="assistant",
                content=resp.content,
                tool_calls=resp.tool_calls,
            )
            chat_messages.append(assistant_msg)

            for tc in resp.tool_calls:
                record = await self._execute_tool(tc, input.task_id)
                tool_records.append(record)

                tool_msg = Message(
                    role="tool",
                    content=str(record.arguments) if record.success else f"错误: {record.arguments}",
                    tool_call_id=tc.id,
                )
                chat_messages.append(tool_msg)

        # 达到最大轮次
        return AgentOutput(
            agent_role=self.role,
            task_id=input.task_id,
            final_message="",
            citations=[],
            tool_calls_made=tool_records,
            finish_reason="max_rounds",
            usage=total_usage,
        )

    async def _execute_tool(
        self, tc: ToolCall, task_id: str
    ) -> ToolInvocationRecord:
        """执行单个工具调用并返回记录。"""
        from mentora.agent_runtime.schemas.context import ToolContext

        import json

        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}

        ctx = ToolContext(
            task_id=task_id,
            agent_role=self.role,
            run_id="",
        )

        result = await self._registry.execute(tc.function.name, args, ctx)

        return ToolInvocationRecord(
            tool_name=tc.function.name,
            arguments=args,
            success=result.success,
            duration_ms=result.duration_ms,
        )

    def _extract_citations(self, resp: ChatResponse) -> list[Citation]:
        """从响应中提取证据引用。"""
        return []
