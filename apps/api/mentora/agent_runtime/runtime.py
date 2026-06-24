"""
Agent Runtime 统一工厂：创建 PromptManager、ToolRegistry、ModelGateway、Orchestrator。

约定：
- HTTP / Celery / 管理命令共用同一套组件初始化逻辑
- 生产环境使用 OpenAIProvider；测试可注入 FakeProvider

@module mentora/agent_runtime/runtime
"""

from __future__ import annotations

from django.conf import settings

from mentora.agent_runtime.agents.clarifier import ClarifierAgent
from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.agents.planner import PlannerAgent
from mentora.agent_runtime.agents.tutor import TutorAgent
from mentora.agent_runtime.context.manager import ContextManager
from mentora.agent_runtime.context.token_counter import TokenCounter
from mentora.agent_runtime.events import EventEmitter
from mentora.agent_runtime.prompts.manager import PromptManager
from mentora.agent_runtime.schemas.task import BudgetConfig
from mentora.agent_runtime.tools.base import ToolDefinition
from mentora.agent_runtime.tools.knowledge_tools import RetrieveEvidenceTool
from mentora.agent_runtime.tools.learning_tools import CreateLearningPlanTool
from mentora.agent_runtime.tools.registry import ToolRegistry
from mentora.model_gateway.gateway import ModelGateway
from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.providers.openai import OpenAIProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.structured_output import StructuredOutputValidator

RETRIEVE_EVIDENCE_DEFINITION = ToolDefinition(
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
    agent_roles={"tutor", "planner"},
)

CREATE_LEARNING_PLAN_DEFINITION = ToolDefinition(
    name="create_learning_plan",
    description=(
        "将生成的学习计划持久化到数据库。"
        "接收完整的计划 JSON（含 phases/units/tasks），"
        "自动创建 Plan → Revision → Phase → Unit → TaskTemplate 结构。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "course_session_id": {
                "type": "string",
                "description": "课程会话 ID（从 query_course_scope 结果获取）",
            },
            "plan_snapshot": {
                "type": "object",
                "description": "计划快照 JSON，包含 phases 数组，每个 phase 含 units，每个 unit 含 tasks",
            },
            "profile_revision_id": {
                "type": "string",
                "description": "课程画像修订 ID（可选）",
            },
            "knowledge_scope_revision_id": {
                "type": "string",
                "description": "知识作用域修订 ID（可选）",
            },
        },
        "required": ["course_session_id", "plan_snapshot"],
    },
    agent_roles={"planner"},
)


def build_tool_registry() -> ToolRegistry:
    """注册领域工具。"""
    registry = ToolRegistry()
    registry.register(RetrieveEvidenceTool(), RETRIEVE_EVIDENCE_DEFINITION)
    registry.register(CreateLearningPlanTool(), CREATE_LEARNING_PLAN_DEFINITION)
    return registry


def build_default_provider() -> BaseProvider:
    """从 settings 构建生产 Provider。"""
    api_key = settings.LLM_API_KEY
    if not api_key:
        raise RuntimeError("LLM_API_KEY 未配置，无法初始化 OpenAIProvider")
    return OpenAIProvider(
        api_key=api_key,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL_BALANCED,
    )


def build_model_gateway(
    provider: BaseProvider | None = None,
    *,
    audit_enabled: bool = True,
) -> ModelGateway:
    """构建 ModelGateway。"""
    provider = provider or build_default_provider()
    router = TaskRouter(default_provider=provider)
    return ModelGateway(
        router=router,
        output_validator=StructuredOutputValidator(),
        audit_enabled=audit_enabled,
        max_retries_per_attempt=settings.LLM_MAX_RETRIES,
    )


def build_context_manager(budget: BudgetConfig | None = None) -> ContextManager:
    return ContextManager(
        budget=budget or BudgetConfig(),
        counter=TokenCounter(),
    )


def build_orchestrator(
    *,
    provider: BaseProvider | None = None,
    prompt_manager: PromptManager | None = None,
    tool_registry: ToolRegistry | None = None,
    context_manager: ContextManager | None = None,
    emitter: EventEmitter | None = None,
    audit_enabled: bool = True,
) -> tuple[Orchestrator, ModelGateway, PromptManager]:
    """构建完整 Orchestrator 及可复用的 gateway / prompt_manager。"""
    prompt_manager = prompt_manager or PromptManager()
    tool_registry = tool_registry or build_tool_registry()
    gateway = build_model_gateway(provider, audit_enabled=audit_enabled)
    context_manager = context_manager or build_context_manager()

    tutor = TutorAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )
    clarifier = ClarifierAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )
    planner = PlannerAgent(
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        model_gateway=gateway,
    )

    orch = Orchestrator(
        agent_map={
            "tutor": tutor,
            "clarifier": clarifier,
            "planner": planner,
        },
        prompt_manager=prompt_manager,
        context_manager=context_manager,
        emitter=emitter or EventEmitter(),
    )
    return orch, gateway, prompt_manager
