"""
Orchestrator：Agent 调度器。

约定：
- 单 Agent 模式：直接路由到指定 Agent 执行
- Pipeline 模式：按 PipelineStep 顺序串联执行
- 所有 Agent 运行通过 RunManager 持久化
- run_stream() 为异步生成器，逐 chunk 产出 SSE 事件字符串

约束：
- 不在此处实现业务逻辑
- Pipeline 模式基础数据结构在 Phase 1 定义，完整实现在 Phase 2

@module mentora/agent_runtime/agents/orchestrator
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Type

from mentora.agent_runtime.agents.base import Agent, AgentInput
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.events import EventEmitter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.context import AgentContext
from mentora.agent_runtime.schemas.output import AgentOutput, OrchestratorResult
from mentora.agent_runtime.schemas.task import OrchestratorTask, PipelineStep


class Orchestrator:
    """Agent 调度器。

    使用方式：
    ```python
    orch = Orchestrator(agent_map={"tutor": tutor_agent}, ...)
    result = await orch.run(task)
    ```
    """

    def __init__(
        self,
        agent_map: dict[str, Agent],
        prompt_manager: PromptManager,
        context_manager: ContextManager,
        emitter: EventEmitter | None = None,
    ):
        self._agents = agent_map
        self._prompts = prompt_manager
        self._context_mgr = context_manager
        self._emitter = emitter or EventEmitter()

    async def run(self, task: OrchestratorTask) -> OrchestratorResult:
        """执行编排任务。"""
        t0 = time.perf_counter()
        self._emitter.agent_run_started(task.id, task.agent_role, task.mode)

        try:
            if task.mode == "pipeline" and task.pipeline_steps:
                outputs = await self._run_pipeline(task)
            else:
                outputs = await self._run_single(task)

            final = outputs[-1] if outputs else None
            duration = (time.perf_counter() - t0) * 1000
            total_calls = sum(len(o.tool_calls_made) for o in outputs)

            result = OrchestratorResult(
                task_id=task.id,
                mode=task.mode,
                status="completed",
                agent_outputs=outputs,
                final_output=final,
                total_duration_ms=duration,
                total_tool_calls=total_calls,
            )
            self._emitter.agent_run_completed(
                task.id, task.agent_role, {"finish_reason": final.finish_reason if final else "unknown"}
            )
            return result

        except Exception as e:
            duration = (time.perf_counter() - t0) * 1000
            self._emitter.agent_run_error(task.id, task.agent_role, "orchestrator_error", str(e))
            return OrchestratorResult(
                task_id=task.id,
                mode=task.mode,
                status="failed",
                total_duration_ms=duration,
                error_code="orchestrator_error",
                error_message=str(e),
            )

    async def run_stream(self, task: OrchestratorTask) -> AsyncGenerator[str, None]:
        """流式执行单 Agent 模式，逐 chunk 产出 SSE 事件字符串。

        产出格式：
        - data: {"type":"chunk","content":"..."}\n\n
        - data: {"type":"done"}\n\n
        - data: {"type":"error","message":"..."}\n\n
        """
        agent = self._get_agent(task.agent_role)
        system_prompt = self._build_system_prompt(agent, task)
        messages, allocation = self._context_mgr.build_messages(
            system_prompt=system_prompt,
            user_message=task.user_message,
            history=task.history_messages,
        )
        ctx = AgentContext(
            messages=messages,
            system_prompt=system_prompt,
            allocation=allocation,
        )
        agent_input = AgentInput(
            task_id=task.id,
            user_message=task.user_message,
            context=ctx,
            max_tool_rounds=task.max_tool_rounds,
        )

        chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
        error_occurred: list[str] = []

        def emitter_callback(event_type: str, payload: dict) -> None:
            if event_type == "agent.response_stream":
                text = payload.get("text_chunk", "")
                is_final = payload.get("is_final", False)
                if is_final:
                    chunk_queue.put_nowait(None)  # sentinel
                elif text:
                    chunk_queue.put_nowait(text)
            elif event_type == "agent.run.error":
                error_occurred.append(payload.get("error_message", "未知错误"))

        emitter = EventEmitter(callback=emitter_callback)

        async def run_agent():
            try:
                await agent.run_stream(agent_input, emitter=emitter)
            except Exception as exc:
                chunk_queue.put_nowait(f"__ERROR__:{exc}")
            finally:
                chunk_queue.put_nowait(None)  # ensure sentinel

        agent_task = asyncio.create_task(run_agent())

        try:
            while True:
                chunk = await chunk_queue.get()
                if chunk is None:
                    break
                if isinstance(chunk, str) and chunk.startswith("__ERROR__:"):
                    err_msg = chunk[len("__ERROR__:"):]
                    yield f"data: {json.dumps({'type': 'error', 'message': err_msg}, ensure_ascii=False)}\n\n"
                    break
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            await agent_task
            if error_occurred:
                yield f"data: {json.dumps({'type': 'error', 'message': error_occurred[0]}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\":\"done\"}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass

    async def _run_single(self, task: OrchestratorTask) -> list[AgentOutput]:
        """执行单 Agent 模式。"""
        agent = self._get_agent(task.agent_role)

        # 组装上下文
        system_prompt = self._build_system_prompt(agent, task)
        messages, allocation = self._context_mgr.build_messages(
            system_prompt=system_prompt,
            user_message=task.user_message,
            history=task.history_messages,
        )

        ctx = AgentContext(
            messages=messages,
            system_prompt=system_prompt,
            allocation=allocation,
        )

        agent_input = AgentInput(
            task_id=task.id,
            user_message=task.user_message,
            context=ctx,
            max_tool_rounds=task.max_tool_rounds,
        )

        output = await agent.run(agent_input)
        self._emitter.agent_response(task.id, output.final_message[:200])
        return [output]

    async def _run_pipeline(self, task: OrchestratorTask) -> list[AgentOutput]:
        """执行 Pipeline 模式（Phase 2 完整实现）。

        约束：
        - 每个 step 失败时记录错误并返回 partial 结果
        - 通过 emitter 发送 step_started / step_completed 事件
        - step 间通过 input_from / output_key 传递中间结果
        """
        outputs: list[AgentOutput] = []
        step_results: dict[str, str] = {}

        for i, step in enumerate(task.pipeline_steps or []):
            self._emitter.step_started(task.id, i, step.agent_role)

            try:
                agent = self._get_agent(step.agent_role)
                user_msg = step.task_instruction
                if step.input_from and step.input_from in step_results:
                    user_msg = f"{user_msg}\n\n上一步结果: {step_results[step.input_from]}"

                system_prompt = self._build_system_prompt(agent, task)
                messages, allocation = self._context_mgr.build_messages(
                    system_prompt=system_prompt,
                    user_message=user_msg,
                )

                ctx = AgentContext(
                    messages=messages,
                    system_prompt=system_prompt,
                    allocation=allocation,
                )

                agent_input = AgentInput(
                    task_id=task.id,
                    user_message=user_msg,
                    context=ctx,
                    max_tool_rounds=step.max_tool_rounds,
                )

                output = await agent.run(agent_input)
                step_results[step.output_key] = output.final_message
                outputs.append(output)

                self._emitter.step_completed(
                    task.id, i, output.final_message[:200]
                )

            except Exception as e:
                # 单步失败：记录错误输出，继续返回 partial 结果
                error_output = AgentOutput(
                    agent_role=step.agent_role,
                    task_id=task.id,
                    final_message="",
                    finish_reason="error",
                )
                outputs.append(error_output)
                self._emitter.agent_run_error(
                    task.id, step.agent_role, "pipeline_step_error", str(e)
                )
                # 不终止 pipeline，让调用方决定如何处理 partial 结果
                # 但记录错误后停止执行后续 step
                break

        return outputs

    def _get_agent(self, role: str) -> Agent:
        """按角色获取 Agent 实例。"""
        if role not in self._agents:
            raise KeyError(f"No agent registered for role '{role}'")
        return self._agents[role]

    def _build_system_prompt(self, agent: Agent, task: OrchestratorTask) -> str:
        """构建 Agent 的系统提示词。"""
        try:
            # 从 PromptManager 获取并渲染模板
            return self._prompts.render(
                agent.system_prompt_ref,
                {"course_name": "当前课程", "source_titles": "，".join(task.context_sources) or "未指定"},
            )
        except KeyError:
            # 模板未找到时返回基础提示词
            return f"你是一个 {agent.role} 角色。请帮助用户完成以下任务。"
