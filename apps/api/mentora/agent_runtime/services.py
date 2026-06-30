"""
RunManager：Agent 运行记录持久化服务。

约定：
- 负责 OrchestratorRun、SubAgentRun、ToolInvocation 的 CRUD
- Agent 运行中实时更新状态和结果
- 不在此处实现业务逻辑

@module mentora/agent_runtime/services
"""

from datetime import datetime, timezone
from typing import Any

from django.db import transaction

from mentora.agent_runtime.models import (
    OrchestratorRun,
    PromptRevision,
    SubAgentRun,
    ToolInvocation,
)


class RunManager:
    """Agent 运行记录管理器。

    使用方式：
    ```python
    manager = RunManager()
    orch_run = manager.create_orchestrator_run(task_input, mode="single", agent_role="tutor")
    sub_run = manager.create_sub_agent_run(orch_run, agent_role="tutor", agent_input={...})
    manager.record_tool_invocation(sub_run, tool_name="retrieve_evidence", ...)
    ```
    """

    def create_orchestrator_run(
        self,
        task_input: dict[str, Any],
        mode: str = "single",
        agent_role: str = "",
    ) -> OrchestratorRun:
        """创建编排运行记录。"""
        return OrchestratorRun.objects.create(
            task_input=task_input,
            mode=mode,
            agent_role=agent_role,
            status="started",
            started_at=datetime.now(timezone.utc),
        )

    def update_orchestrator_status(
        self,
        run: OrchestratorRun,
        status: str,
        output: dict[str, Any] | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> OrchestratorRun:
        """更新编排运行状态。"""
        run.status = status
        if status in ("completed", "failed"):
            run.completed_at = datetime.now(timezone.utc)
        if output is not None:
            run.output_json = output
        if error_code:
            run.error_code = error_code
        if error_message:
            run.error_message = error_message
        run.save(update_fields=[
            "status", "completed_at", "output_json",
            "error_code", "error_message",
        ])
        return run

    def create_sub_agent_run(
        self,
        orchestrator_run: OrchestratorRun,
        agent_role: str,
        agent_input: dict[str, Any],
    ) -> SubAgentRun:
        """创建子 Agent 运行记录。"""
        return SubAgentRun.objects.create(
            orchestrator_run=orchestrator_run,
            agent_role=agent_role,
            agent_input=agent_input,
            status="started",
            started_at=datetime.now(timezone.utc),
        )

    def update_sub_agent_run(
        self,
        run: SubAgentRun,
        status: str,
        agent_output: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        tool_rounds: int | None = None,
        duration_ms: int | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> SubAgentRun:
        """更新子 Agent 运行状态和结果。"""
        run.status = status
        if status in ("completed", "failed"):
            run.completed_at = datetime.now(timezone.utc)
        if agent_output is not None:
            run.agent_output = agent_output
        if usage is not None:
            run.usage_json = usage
        if tool_rounds is not None:
            run.tool_rounds = tool_rounds
        if duration_ms is not None:
            run.duration_ms = duration_ms
        if error_code:
            run.error_code = error_code
        if error_message:
            run.error_message = error_message
        run.save(update_fields=[
            "status", "completed_at", "agent_output",
            "usage_json", "tool_rounds", "duration_ms",
            "error_code", "error_message",
        ])
        return run

    def record_tool_invocation(
        self,
        sub_agent_run: SubAgentRun,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any] | None = None,
        success: bool = False,
        duration_ms: int | None = None,
        artifact_ref: str = "",
    ) -> ToolInvocation:
        """记录单次工具调用。"""
        return ToolInvocation.objects.create(
            sub_agent_run=sub_agent_run,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
            artifact_ref=artifact_ref,
        )

    def get_or_create_prompt_revision(
        self,
        template_name: str,
        version: str,
        rendered_prompt: str,
    ) -> PromptRevision:
        """获取或创建提示词版本记录。"""
        import hashlib

        content_hash = hashlib.sha256(rendered_prompt.encode()).hexdigest()

        rev, created = PromptRevision.objects.get_or_create(
            template_name=template_name,
            version=version,
            defaults={
                "content_sha256": content_hash,
                "rendered_prompt": rendered_prompt,
            },
        )
        return rev
