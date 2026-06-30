"""
Workflow Runtime Celery 任务。

约定：
- run_workflow 接收 workflow_id，从 DB 加载状态后执行
- 执行前后通过 WorkflowRuntime 更新状态机
- 队列路由名：agent

@module mentora/workflow_runtime/tasks
"""

import asyncio
import logging

from celery import shared_task

from mentora.agent_runtime.runtime import build_orchestrator
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.workflow_runtime.services import WorkflowRuntime

logger = logging.getLogger(__name__)

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator, _, _ = build_orchestrator()
    return _orchestrator


@shared_task(
    name="mentora.workflow_runtime.tasks.run_workflow",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_workflow(self, workflow_id: str) -> dict:
    """执行工作流——从 DB 加载状态，运行编排，写回结果。

    失败时自动重试（最多 2 次，间隔 30 秒）。
    """
    runtime = WorkflowRuntime()

    wf = runtime.get(workflow_id)
    if wf is None:
        logger.error("Workflow %s not found", workflow_id)
        return {"workflow_id": workflow_id, "status": "error", "error": "not_found"}

    if wf.status != "pending":
        return {"workflow_id": workflow_id, "status": "skipped", "reason": f"already {wf.status}"}

    # 推进到 running
    runtime.checkpoint(workflow_id, step_index=0, data={"status": "started"})
    WorkflowState = type(wf)
    WorkflowState.objects.filter(id=workflow_id).update(status="running")

    try:
        task = OrchestratorTask.model_validate(wf.input_json)
    except Exception as exc:
        runtime.fail(workflow_id, error_code="invalid_input", error_message=str(exc))
        return {"workflow_id": workflow_id, "status": "error", "error": f"invalid input: {exc}"}

    try:
        orch = _get_orchestrator()
        result = asyncio.run(orch.run(task))
        runtime.complete(workflow_id, output_json=result.model_dump(mode="json"))
        return {
            "workflow_id": workflow_id,
            "status": result.status,
            "total_duration_ms": result.total_duration_ms,
            "total_tool_calls": result.total_tool_calls,
        }
    except Exception as exc:
        logger.exception("Workflow %s failed", workflow_id)
        runtime.fail(
            workflow_id,
            error_code="runtime_error",
            error_message=str(exc),
        )
        raise self.retry(exc=exc)
