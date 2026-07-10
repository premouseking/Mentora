"""
Agent 运行时审计模型：编排运行、子 Agent 运行、工具调用和提示词版本。

约定：
- OrchestratorRun 记录每次编排任务的完整生命周期
- SubAgentRun 记录单个 Agent 的运行（输入/输出/Token 用量）
- ToolInvocation 记录每次工具调用的参数和结果
- PromptRevision 记录提示词版本快照

约束：
- 审计模型不参与业务逻辑
- task_input / agent_input / agent_output 使用 JSONB 字段
- agent_runtime 模块不引用 domain 模型

@see docs/architecture/agent-runtime-design.md §8.1
@module mentora/agent_runtime/models
"""

import uuid

from django.db import models


class OrchestratorRun(models.Model):
    """每次编排任务的运行记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_input = models.JSONField(help_text="OrchestratorTask 快照")
    mode = models.CharField(max_length=16, help_text="single / pipeline")
    status = models.CharField(
        max_length=16,
        default="started",
        help_text="started / running / completed / failed",
    )
    agent_role = models.CharField(max_length=32, help_text="主 Agent 角色")
    prompt_revision_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="使用的提示词版本 ID",
    )
    context_allocation = models.JSONField(
        null=True,
        blank=True,
        help_text="上下文分配快照",
    )
    output_json = models.JSONField(
        null=True,
        blank=True,
        help_text="OrchestratorResult 快照",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_duration_ms = models.IntegerField(null=True, blank=True)
    total_tool_calls = models.IntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_orchestrator_run"
        verbose_name = "编排运行"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=["agent_role", "status"],
                name="ar_orch_role_status_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="ar_orch_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"OrchestratorRun({self.id}) {self.mode} {self.status}"


class SubAgentRun(models.Model):
    """单个 Agent 的运行记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orchestrator_run = models.ForeignKey(
        OrchestratorRun,
        on_delete=models.CASCADE,
        related_name="sub_runs",
        help_text="所属编排运行",
    )
    agent_role = models.CharField(max_length=32, help_text="Agent 角色")
    agent_input = models.JSONField(help_text="AgentInput 快照")
    agent_output = models.JSONField(null=True, blank=True, help_text="AgentOutput 快照")
    prompt_revision_id = models.CharField(
        max_length=64, blank=True, default="", help_text="使用的提示词版本 ID"
    )
    status = models.CharField(
        max_length=16,
        default="started",
        help_text="started / running / completed / failed",
    )
    duration_ms = models.IntegerField(null=True, blank=True)
    tool_rounds = models.IntegerField(default=0, help_text="工具调用轮次数")
    usage_json = models.JSONField(
        null=True,
        blank=True,
        help_text="TokenUsage 快照 {prompt_tokens, completion_tokens, total_tokens}",
    )
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_sub_agent_run"
        verbose_name = "子 Agent 运行"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=["orchestrator_run", "agent_role"],
                name="ar_sub_orch_role_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="ar_sub_status_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"SubAgentRun({self.id}) {self.agent_role} {self.status}"


class ToolInvocation(models.Model):
    """单次工具调用记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_agent_run = models.ForeignKey(
        SubAgentRun,
        on_delete=models.CASCADE,
        related_name="tool_invocations",
        help_text="所属子 Agent 运行",
    )
    tool_name = models.CharField(max_length=64, help_text="工具名称")
    arguments = models.JSONField(help_text="工具参数")
    result = models.JSONField(null=True, blank=True, help_text="工具结果")
    success = models.BooleanField(default=False, help_text="是否执行成功")
    duration_ms = models.IntegerField(null=True, blank=True)
    artifact_ref = models.CharField(
        max_length=512, blank=True, default="", help_text="大结果 Artifact 引用"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_tool_invocation"
        verbose_name = "工具调用"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=["sub_agent_run", "tool_name"],
                name="ar_tool_sub_name_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"ToolInvocation({self.id}) {self.tool_name} {'✓' if self.success else '✗'}"


class PromptRevision(models.Model):
    """提示词版本快照，审计 Agent 用哪个版本运行。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_name = models.CharField(max_length=64, help_text="模板名称")
    version = models.CharField(max_length=16, help_text="语义版本号")
    content_sha256 = models.CharField(max_length=64, help_text="提示词内容 SHA-256")
    rendered_prompt = models.TextField(help_text="渲染后的完整系统提示词")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_prompt_revision"
        verbose_name = "提示词版本"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["template_name", "version"],
                name="ar_promptrev_name_version_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"PromptRevision({self.template_name}) v{self.version}"


class CourseAgentSession(models.Model):
    """课程绑定的 Agent 对话会话。

    约定：
    - course_id / course_session_id 存 UUID 字符串，不跨模块 FK
    - 首条用户消息发送时创建，关闭页面后可恢复历史

    约束：
    - 会话必须归属单一课程
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "进行中"
        ARCHIVED = "archived", "已归档"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_id = models.UUIDField(db_index=True, help_text="Course.id")
    course_session_id = models.UUIDField(db_index=True, help_text="CourseCreationSession.id")
    legacy_owner_id = models.CharField(
        max_length=128, blank=True, default="", help_text="用户 ID（预留）",
    )
    owner = models.ForeignKey(
        "users.User", null=True, on_delete=models.PROTECT, related_name="course_agent_sessions",
    )
    title = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_runtime_course_agent_session"
        verbose_name = "课程 Agent 会话"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["course_id", "-updated_at"], name="ar_cas_course_updated_idx"),
            models.Index(fields=["course_session_id", "-updated_at"], name="ar_cas_session_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"CourseAgentSession({self.id}) course={self.course_id}"


class CourseAgentMessage(models.Model):
    """课程 Agent 会话消息。"""

    class Role(models.TextChoices):
        USER = "user", "用户"
        ASSISTANT = "assistant", "助手"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CourseAgentSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True, default="")
    citations_json = models.JSONField(default=list, help_text="引用列表")
    metadata_json = models.JSONField(default=dict, help_text="mentions 等扩展元数据")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_course_agent_message"
        verbose_name = "课程 Agent 消息"
        verbose_name_plural = verbose_name
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"], name="ar_cam_session_created_idx"),
        ]

    def __str__(self) -> str:
        preview = self.content[:40] + "…" if len(self.content) > 40 else self.content
        return f"CourseAgentMessage({self.role}) {preview}"
