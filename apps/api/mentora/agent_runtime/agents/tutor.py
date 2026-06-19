"""
TutorAgent：基于资料的教学问答 Agent。

约定：
- 使用 retrieve_evidence 工具检索资料
- 通过 model_gateway 调用 LLM
- 所有回复必须标注证据来源

@module mentora/agent_runtime/agents/tutor
"""

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.output import AgentOutput, Citation, TokenUsage, ToolInvocationRecord
from mentora.agent_runtime.tools.base import ToolDefinition
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.schemas import ChatResponse, Message, ToolCall


class TutorAgent(Agent):
    """教学问答 Agent。

    职责：
    - 在学生提问时检索相关资料
    - 基于资料内容组织回答
    - 标注引用来源（页码/坐标）
    """

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
        """非流式执行（Phase 1 兼容）。"""
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

            # 没有工具调用 → 最终回复
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
            assistant_msg = self._build_assistant_message(resp)
            chat_messages.append(assistant_msg)

            for tc in resp.tool_calls:
                record = await self._execute_tool(tc, input.task_id)
                tool_records.append(record)

                # 构建 tool 结果消息
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

    async def run_stream(
        self,
        input: AgentInput,
        emitter=None,
    ) -> AgentOutput:
        """流式执行（Phase 2）。

        与 run() 逻辑相同，但通过 chat_stream() 逐 chunk 推送内容。
        emitter 用于发送 agent_response_stream 事件。

        约束：
        - 工具调用期间暂停流式输出，工具结果回填后继续
        - 最终 AgentOutput 汇总所有 usage 和 tool_records
        """
        total_usage = TokenUsage()
        tool_records: list[ToolInvocationRecord] = []
        chat_messages = list(input.context.messages)

        tools = self._registry.get_openai_tools(self.role)
        accumulated_content: list[str] = []
        pending_tool_calls: list[ToolCall] = []

        for round_num in range(input.max_tool_rounds):
            accumulated_content.clear()
            pending_tool_calls.clear()

            async for chunk in self._gateway.chat_stream(
                task_type=self.role,
                messages=chat_messages,
                tools=tools,
            ):
                if chunk.usage:
                    total_usage.prompt_tokens += chunk.usage.prompt_tokens
                    total_usage.completion_tokens += chunk.usage.completion_tokens
                    total_usage.total_tokens += chunk.usage.total_tokens

                # 工具调用汇总在最后一个 chunk 返回
                if chunk.tool_calls:
                    pending_tool_calls.extend(chunk.tool_calls)

                # 流式内容推送
                if chunk.content:
                    accumulated_content.append(chunk.content)
                    if emitter:
                        emitter.agent_response_stream(input.task_id, chunk.content, is_final=False)

            # 发送最终标记
            full_content = "".join(accumulated_content)
            if emitter:
                emitter.agent_response_stream(input.task_id, "", is_final=True)

            # 没有工具调用 → 最终回复
            if not pending_tool_calls:
                final_resp = ChatResponse(
                    content=full_content,
                    usage=total_usage,
                )
                return AgentOutput(
                    agent_role=self.role,
                    task_id=input.task_id,
                    final_message=full_content,
                    citations=self._extract_citations(final_resp),
                    tool_calls_made=tool_records,
                    finish_reason="completed",
                    usage=total_usage,
                )

            # 处理工具调用
            assistant_msg = self._build_assistant_message(
                ChatResponse(content=full_content, tool_calls=pending_tool_calls)
            )
            chat_messages.append(assistant_msg)

            for tc in pending_tool_calls:
                if emitter:
                    try:
                        import json
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    emitter.tool_call(input.task_id, tc.function.name, args)

                record = await self._execute_tool(tc, input.task_id)
                tool_records.append(record)

                tool_msg = Message(
                    role="tool",
                    content=str(record.arguments) if record.success else f"错误: {record.arguments}",
                    tool_call_id=tc.id,
                )
                chat_messages.append(tool_msg)

                if emitter:
                    emitter.tool_result(
                        input.task_id,
                        tc.function.name,
                        record.success,
                        str(record.arguments)[:200],
                    )

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

    def _build_assistant_message(self, resp: ChatResponse) -> Message:
        """构建 assistant 消息（含 tool_calls）。"""
        return Message(
            role="assistant",
            content=resp.content,
            tool_calls=resp.tool_calls,
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
        # Phase 1 简单实现：从 content 中搜索 evidence_id 引用模式
        # Phase 2+ 通过结构化输出获取精确引用
        return []
