"""
Orchestrator：Agent 调度器。

约定：
- 单 Agent 模式：直接路由到指定 Agent 执行
- Pipeline 模式：按 PipelineStep 顺序串联执行
- run_stream() 为异步生成器，逐 chunk 产出 SSE 事件字符串

约束：
- 不在此处实现业务逻辑

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
from mentora.agent_runtime.services import RunManager
from mentora.agent_runtime.models import OrchestratorRun


def _tool_status_messages(tool_name: str, *, running: bool, success: bool | None = None) -> str:
    """按工具类型生成用户可见的状态文案。"""
    if tool_name == "query_course_scope":
        if running:
            return "正在查询课程资料范围"
        return "资料范围查询完成" if success else "资料范围查询失败"
    if tool_name == "retrieve_evidence":
        if running:
            return "正在检索资料"
        return "资料检索完成" if success else "资料检索失败"
    if running:
        return "正在调用工具"
    return "工具调用完成" if success else "工具调用失败"


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
        run_manager: RunManager | None = None,
    ):
        self._agents = agent_map
        self._prompts = prompt_manager
        self._context_mgr = context_manager
        self._emitter = emitter or EventEmitter()
        self._run_manager = run_manager or RunManager()

    async def run(self, task: OrchestratorTask) -> OrchestratorResult:
        """执行编排任务。"""
        t0 = time.perf_counter()
        self._emitter.agent_run_started(task.id, task.agent_role, task.mode)

        orch_run = self._run_manager.create_orchestrator_run(
            task.model_dump(mode="json"),
            mode=task.mode,
            agent_role=task.agent_role or "",
        )

        try:
            if task.mode == "pipeline" and task.pipeline_steps:
                outputs = await self._run_pipeline(task, orch_run)
                has_error = any(o.finish_reason == "error" for o in outputs)
                status = "failed" if has_error else "completed"
            else:
                outputs = await self._run_single(task, orch_run)
                status = "completed"

            final = outputs[-1] if outputs else None
            duration = (time.perf_counter() - t0) * 1000
            total_calls = sum(len(o.tool_calls_made) for o in outputs)

            result = OrchestratorResult(
                task_id=task.id,
                mode=task.mode,
                status=status,
                agent_outputs=outputs,
                final_output=final,
                total_duration_ms=duration,
                total_tool_calls=total_calls,
            )
            self._run_manager.update_orchestrator_status(
                orch_run,
                status,
                output=result.model_dump(mode="json"),
            )
            if status == "completed":
                self._emitter.agent_run_completed(
                    task.id, task.agent_role, {"finish_reason": final.finish_reason if final else "unknown"}
                )
            return result

        except Exception as e:
            duration = (time.perf_counter() - t0) * 1000
            self._emitter.agent_run_error(task.id, task.agent_role, "orchestrator_error", str(e))
            self._run_manager.update_orchestrator_status(
                orch_run,
                "failed",
                error_code="orchestrator_error",
                error_message=str(e),
            )
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
        - data: {"type":"content","content":"..."}\n\n
        - data: {"type":"done"}\n\n
        - data: {"type":"error","message":"..."}\n\n
        """
        orch_run = self._run_manager.create_orchestrator_run(
            task.model_dump(mode="json"),
            mode=task.mode,
            agent_role=task.agent_role or "",
        )
        sub_run = self._run_manager.create_sub_agent_run(
            orch_run,
            task.agent_role,
            {"user_message": task.user_message},
        )

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
            model_id=task.model_id,
            max_tool_rounds=task.max_tool_rounds,
            audit_sub_agent_run_id=str(sub_run.id),
        )

        event_queue: asyncio.Queue[dict | None] = asyncio.Queue()
        error_occurred: list[str] = []

        def emitter_callback(event_type: str, payload: dict) -> None:
            if event_type == "agent.response_stream":
                text = payload.get("text_chunk", "")
                if text:
                    # Wire 对齐 LightRead：type=content
                    event_queue.put_nowait({"type": "content", "content": text})
            elif event_type == "agent.thinking":
                round_number = payload.get("round_number", 0)
                event_queue.put_nowait({
                    "type": "status",
                    "status_key": f"thinking:{round_number}",
                    "event": event_type,
                    "phase": "thinking",
                    "state": "running",
                    "message": "正在思考…",
                })
            elif event_type == "agent.tool.call":
                tool_name = payload.get("tool_name", "")
                event_queue.put_nowait({
                    "type": "status",
                    "status_key": f"tool:{tool_name or 'unknown'}",
                    "event": event_type,
                    "phase": "tool",
                    "state": "running",
                    "tool_name": tool_name,
                    "message": _tool_status_messages(tool_name, running=True),
                    "arguments": payload.get("arguments", {}),
                })
            elif event_type == "agent.tool.result":
                tool_name = payload.get("tool_name", "")
                success = payload.get("success", False)
                event_queue.put_nowait({
                    "type": "status",
                    "status_key": f"tool:{tool_name or 'unknown'}",
                    "event": event_type,
                    "phase": "tool",
                    "state": "completed" if success else "failed",
                    "tool_name": tool_name,
                    "success": success,
                    "message": _tool_status_messages(tool_name, running=False, success=success),
                    "preview": payload.get("preview", ""),
                    "arguments": payload.get("arguments"),
                })
                citations = payload.get("citations") or []
                if citations:
                    event_queue.put_nowait({
                        "type": "citations",
                        "tool_name": payload.get("tool_name", ""),
                        "citations": citations,
                    })
            elif event_type == "agent.run.error":
                error_occurred.append(payload.get("error_message", "未知错误"))

        emitter = EventEmitter(callback=emitter_callback)

        async def run_agent():
            try:
                output = await agent.run_stream(agent_input, emitter=emitter)
                self._run_manager.update_sub_agent_run(
                    sub_run,
                    "completed",
                    agent_output=output.model_dump(mode="json"),
                    tool_rounds=len(output.tool_calls_made),
                    usage=output.usage.model_dump(mode="json") if output.usage else None,
                )
            except Exception as exc:
                self._run_manager.update_sub_agent_run(
                    sub_run,
                    "failed",
                    error_message=str(exc),
                )
                event_queue.put_nowait({"type": "error", "message": str(exc)})
            finally:
                event_queue.put_nowait(None)  # ensure sentinel

        agent_task = asyncio.create_task(run_agent())

        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                if event.get("type") == "error":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            await agent_task
            if error_occurred:
                self._run_manager.update_orchestrator_status(
                    orch_run,
                    "failed",
                    error_code="agent_stream_error",
                    error_message=error_occurred[0],
                )
                yield f"data: {json.dumps({'type': 'error', 'message': error_occurred[0]}, ensure_ascii=False)}\n\n"
            else:
                self._run_manager.update_orchestrator_status(orch_run, "completed")
            yield "data: {\"type\":\"done\"}\n\n"
        except Exception as exc:
            self._run_manager.update_orchestrator_status(
                orch_run,
                "failed",
                error_code="orchestrator_stream_error",
                error_message=str(exc),
            )
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass

    async def _run_single(
        self, task: OrchestratorTask, orch_run: OrchestratorRun
    ) -> list[AgentOutput]:
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

        sub_run = self._run_manager.create_sub_agent_run(
            orch_run,
            task.agent_role,
            {"user_message": task.user_message},
        )

        agent_input = AgentInput(
            task_id=task.id,
            user_message=task.user_message,
            context=ctx,
            model_id=task.model_id,
            max_tool_rounds=task.max_tool_rounds,
            audit_sub_agent_run_id=str(sub_run.id),
        )

        try:
            output = await agent.run(agent_input)
            self._run_manager.update_sub_agent_run(
                sub_run,
                "completed",
                agent_output=output.model_dump(mode="json"),
                tool_rounds=len(output.tool_calls_made),
                usage=output.usage.model_dump(mode="json") if output.usage else None,
            )
        except Exception as exc:
            self._run_manager.update_sub_agent_run(
                sub_run,
                "failed",
                error_message=str(exc),
            )
            raise

        self._emitter.agent_response(task.id, output.final_message[:200])
        return [output]

    async def _run_pipeline(
        self, task: OrchestratorTask, orch_run: OrchestratorRun
    ) -> list[AgentOutput]:
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
                    model_id=task.model_id,
                    max_tool_rounds=step.max_tool_rounds,
                )

                sub_run = self._run_manager.create_sub_agent_run(
                    orch_run,
                    step.agent_role,
                    {"user_message": user_msg, "pipeline_step": i},
                )
                agent_input = agent_input.model_copy(
                    update={"audit_sub_agent_run_id": str(sub_run.id)},
                )

                try:
                    output = await agent.run(agent_input)
                    self._run_manager.update_sub_agent_run(
                        sub_run,
                        "completed",
                        agent_output=output.model_dump(mode="json"),
                        tool_rounds=len(output.tool_calls_made),
                        usage=output.usage.model_dump(mode="json") if output.usage else None,
                    )
                except Exception as step_exc:
                    self._run_manager.update_sub_agent_run(
                        sub_run,
                        "failed",
                        error_message=str(step_exc),
                    )
                    raise
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
            raise KeyError(
                f"Prompt template not found for agent '{agent.system_prompt_ref}'"
            ) from None
