"""
Agent Runtime Celery 任务。

约定：
- run_agent 接收 OrchestratorTask JSON，返回 OrchestratorResult JSON
- 队列路由名：agent

@module mentora/agent_runtime/tasks
"""

import asyncio

from celery import shared_task
from django.conf import settings

from mentora.agent_runtime.runtime import build_orchestrator
from mentora.agent_runtime.schemas.task import OrchestratorTask

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        if not settings.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY 未配置，无法执行 Agent 任务")
        _orchestrator, _, _ = build_orchestrator()
    return _orchestrator


@shared_task(name="mentora.agent_runtime.tasks.run_agent")
def run_agent(task_json: str) -> dict:
    """Agent 运行 Celery 桥接。"""
    task = OrchestratorTask.model_validate_json(task_json)
    orch = _get_orchestrator()
    orch._context_mgr.budget = task.budget_config
    result = asyncio.run(orch.run(task))
    return result.model_dump(mode="json")
