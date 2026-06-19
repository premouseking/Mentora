"""
Agent Runtime Celery 任务。

约定：
- run_agent 接收 OrchestratorTask JSON，返回 OrchestratorResult JSON
- 所有 Agent 运行通过 Celery 异步执行
- 队列路由名：agent

@module mentora/agent_runtime/tasks
"""

import asyncio

from celery import shared_task

from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.agents.tutor import TutorAgent
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.events import EventEmitter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.agent_runtime.tools.base import ToolDefinition
from mentora.agent_runtime.tools.knowledge_tools import RetrieveEvidenceTool
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.fake import FakeProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.structured_output import StructuredOutputValidator


def _build_agent_runtime():
    """构建 Agent Runtime 的所有组件（工厂函数）。"""
    # 模型网关
    router = TaskRouter(default_provider=FakeProvider())
    gateway = ModelGateway(router=router, output_validator=StructuredOutputValidator())

    # 提示词管理
    prompt_mgr = PromptManager()

    # 工具注册表
    registry = ToolRegistry()
    registry.register(
        RetrieveEvidenceTool(),
        ToolDefinition(
            name="retrieve_evidence",
            description="搜索学习资料中的相关内容。用于查找课程资料的原文证据。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询文本",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            agent_roles={"tutor", "planner", "assessor"},
        ),
    )

    # Agent 映射
    tutor = TutorAgent(
        prompt_manager=prompt_mgr,
        tool_registry=registry,
        model_gateway=gateway,
    )
    agent_map = {"tutor": tutor}

    # 上下文管理
    counter = TokenCounter()
    ctx_mgr = ContextManager(
        budget=OrchestratorTask().budget_config,
        counter=counter,
    )

    # 事件发射器
    emitter = EventEmitter()

    orch = Orchestrator(
        agent_map=agent_map,
        prompt_manager=prompt_mgr,
        context_manager=ctx_mgr,
        emitter=emitter,
    )
    return orch


# 模块级单例（懒加载）
_orchestrator: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _build_agent_runtime()
    return _orchestrator


@shared_task(name="mentora.agent_runtime.tasks.run_workflow")
def run_workflow(workflow_id: str) -> dict[str, str]:
    """Celery bridge for the explicit workflow state machine."""
    return {"workflow_id": workflow_id, "status": "accepted"}


@shared_task(name="mentora.agent_runtime.tasks.run_agent")
def run_agent(task_json: str) -> dict:
    """Agent 运行 Celery 桥接。

    参数：
    - task_json: OrchestratorTask 的 JSON 序列化

    返回：OrchestratorResult dict
    """
    task = OrchestratorTask.model_validate_json(task_json)
    orch = _get_orchestrator()
    # 更新预算配置
    orch._context_mgr.budget = task.budget_config
    result = asyncio.run(orch.run(task))
    return result.model_dump(mode="json")
