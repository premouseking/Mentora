# Generated migration for agent_runtime audit models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="OrchestratorRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("task_input", models.JSONField(help_text="OrchestratorTask 快照")),
                (
                    "mode",
                    models.CharField(
                        help_text="single / pipeline", max_length=16
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default="started",
                        help_text="started / running / completed / failed",
                        max_length=16,
                    ),
                ),
                (
                    "agent_role",
                    models.CharField(help_text="主 Agent 角色", max_length=32),
                ),
                (
                    "prompt_revision_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="使用的提示词版本 ID",
                        max_length=64,
                    ),
                ),
                (
                    "context_allocation",
                    models.JSONField(
                        blank=True, help_text="上下文分配快照", null=True
                    ),
                ),
                (
                    "output_json",
                    models.JSONField(
                        blank=True,
                        help_text="OrchestratorResult 快照",
                        null=True,
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("total_duration_ms", models.IntegerField(blank=True, null=True)),
                ("total_tool_calls", models.IntegerField(default=0)),
                (
                    "error_code",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "error_message",
                    models.TextField(blank=True, default=""),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "agent_runtime_orchestrator_run",
                "verbose_name": "编排运行",
                "verbose_name_plural": "编排运行",
            },
        ),
        migrations.CreateModel(
            name="PromptRevision",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "template_name",
                    models.CharField(help_text="模板名称", max_length=64),
                ),
                (
                    "version",
                    models.CharField(help_text="语义版本号", max_length=16),
                ),
                (
                    "content_sha256",
                    models.CharField(help_text="提示词内容 SHA-256", max_length=64),
                ),
                (
                    "rendered_prompt",
                    models.TextField(help_text="渲染后的完整系统提示词"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "agent_runtime_prompt_revision",
                "verbose_name": "提示词版本",
                "verbose_name_plural": "提示词版本",
            },
        ),
        migrations.CreateModel(
            name="SubAgentRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "agent_role",
                    models.CharField(help_text="Agent 角色", max_length=32),
                ),
                ("agent_input", models.JSONField(help_text="AgentInput 快照")),
                (
                    "agent_output",
                    models.JSONField(
                        blank=True, help_text="AgentOutput 快照", null=True
                    ),
                ),
                (
                    "prompt_revision_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="使用的提示词版本 ID",
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default="started",
                        help_text="started / running / completed / failed",
                        max_length=16,
                    ),
                ),
                ("duration_ms", models.IntegerField(blank=True, null=True)),
                (
                    "tool_rounds",
                    models.IntegerField(default=0, help_text="工具调用轮次数"),
                ),
                (
                    "usage_json",
                    models.JSONField(
                        blank=True,
                        help_text="TokenUsage 快照 {prompt_tokens, completion_tokens, total_tokens}",
                        null=True,
                    ),
                ),
                (
                    "error_code",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "error_message",
                    models.TextField(blank=True, default=""),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "orchestrator_run",
                    models.ForeignKey(
                        help_text="所属编排运行",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sub_runs",
                        to="agent_runtime.orchestratorrun",
                    ),
                ),
            ],
            options={
                "db_table": "agent_runtime_sub_agent_run",
                "verbose_name": "子 Agent 运行",
                "verbose_name_plural": "子 Agent 运行",
            },
        ),
        migrations.CreateModel(
            name="ToolInvocation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "tool_name",
                    models.CharField(help_text="工具名称", max_length=64),
                ),
                ("arguments", models.JSONField(help_text="工具参数")),
                (
                    "result",
                    models.JSONField(
                        blank=True, help_text="工具结果", null=True
                    ),
                ),
                (
                    "success",
                    models.BooleanField(default=False, help_text="是否执行成功"),
                ),
                ("duration_ms", models.IntegerField(blank=True, null=True)),
                (
                    "artifact_ref",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="大结果 Artifact 引用",
                        max_length=512,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "sub_agent_run",
                    models.ForeignKey(
                        help_text="所属子 Agent 运行",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_invocations",
                        to="agent_runtime.subagentrun",
                    ),
                ),
            ],
            options={
                "db_table": "agent_runtime_tool_invocation",
                "verbose_name": "工具调用",
                "verbose_name_plural": "工具调用",
            },
        ),
        migrations.AddIndex(
            model_name="orchestratorrun",
            index=models.Index(
                fields=["agent_role", "status"],
                name="ar_orch_role_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="orchestratorrun",
            index=models.Index(
                fields=["created_at"],
                name="ar_orch_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="subagentrun",
            index=models.Index(
                fields=["orchestrator_run", "agent_role"],
                name="ar_sub_orch_role_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="subagentrun",
            index=models.Index(
                fields=["status", "created_at"],
                name="ar_sub_status_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="toolinvocation",
            index=models.Index(
                fields=["sub_agent_run", "tool_name"],
                name="ar_tool_sub_name_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="promptrevision",
            constraint=models.UniqueConstraint(
                fields=["template_name", "version"],
                name="ar_promptrev_name_version_unique",
            ),
        ),
    ]
