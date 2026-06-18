"""
SSE 事件发射器。

约定：
- 所有事件通过回调函数发射（无状态，不持有连接）
- 事件命名规范：agent.{模块}.{动作}
- payload 可 JSON 序列化

约束：
- 不持有 WebSocket/SSE 连接
- 事件历史由 runtime_events 模块持久化（Phase 2+）

@module mentora/agent_runtime/events
"""

import json
import time
from typing import Any, Callable


class EventEmitter:
    """SSE 事件发射器。

    使用方式：
    ```python
    emitter = EventEmitter(callback=my_send_to_sse)
    emitter.agent_run_started(task_id="t1", agent_role="tutor")
    ```
    """

    def __init__(self, callback: Callable[[str, dict], None] | None = None):
        self._callback = callback or self._noop

    @staticmethod
    def _noop(event: str, payload: dict) -> None:
        pass

    def _emit(self, event_type: str, payload: dict) -> None:
        """发射事件（内部方法）。

        统一为 payload 注入时间戳和事件类型。
        """
        payload["event"] = event_type
        payload["timestamp"] = time.time()
        try:
            self._callback(event_type, payload)
        except Exception:
            # SSE 回调错误不应影响 Agent 主流程
            pass

    # ── agent.run 事件 ──

    def agent_run_started(self, task_id: str, agent_role: str, mode: str = "single") -> None:
        self._emit("agent.run.started", {
            "task_id": task_id,
            "agent_role": agent_role,
            "mode": mode,
        })

    def agent_run_completed(self, task_id: str, agent_role: str, output_summary: dict) -> None:
        self._emit("agent.run.completed", {
            "task_id": task_id,
            "agent_role": agent_role,
            "output_summary": output_summary,
        })

    def agent_run_error(self, task_id: str, agent_role: str, error_code: str, error_message: str) -> None:
        self._emit("agent.run.error", {
            "task_id": task_id,
            "agent_role": agent_role,
            "error_code": error_code,
            "error_message": error_message,
        })

    # ── agent.thinking 事件 ──

    def agent_thinking(self, task_id: str, round_number: int) -> None:
        self._emit("agent.thinking", {
            "task_id": task_id,
            "round_number": round_number,
        })

    def agent_response(self, task_id: str, text_chunk: str) -> None:
        self._emit("agent.response", {
            "task_id": task_id,
            "text_chunk": text_chunk,
        })

    # ── agent.tool 事件 ──

    def tool_call(self, task_id: str, tool_name: str, arguments: dict) -> None:
        self._emit("agent.tool.call", {
            "task_id": task_id,
            "tool_name": tool_name,
            "arguments": arguments,
        })

    def tool_result(self, task_id: str, tool_name: str, success: bool, preview: str) -> None:
        self._emit("agent.tool.result", {
            "task_id": task_id,
            "tool_name": tool_name,
            "success": success,
            "preview": preview,
        })

    # ── agent.response_stream 事件（Phase 2 流式）──

    def agent_response_stream(self, task_id: str, text_chunk: str, is_final: bool = False) -> None:
        self._emit("agent.response_stream", {
            "task_id": task_id,
            "text_chunk": text_chunk,
            "is_final": is_final,
        })

    # ── agent.step 事件（Phase 2 Pipeline）──

    def step_started(self, task_id: str, step_index: int, agent_role: str) -> None:
        self._emit("agent.step.started", {
            "task_id": task_id,
            "step_index": step_index,
            "agent_role": agent_role,
        })

    def step_completed(self, task_id: str, step_index: int, output_preview: str) -> None:
        self._emit("agent.step.completed", {
            "task_id": task_id,
            "step_index": step_index,
            "output_preview": output_preview[:200],
        })
