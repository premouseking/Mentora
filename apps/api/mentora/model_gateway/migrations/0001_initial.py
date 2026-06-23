# Generated migration for model_gateway initial models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="ModelRequest",
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
                    "task_type",
                    models.CharField(
                        db_index=True,
                        help_text="任务类型：tutor / planner / assessor",
                        max_length=32,
                    ),
                ),
                (
                    "provider_name",
                    models.CharField(
                        help_text="路由到的 Provider 名称", max_length=32
                    ),
                ),
                (
                    "messages_json",
                    models.JSONField(help_text="发送给模型的消息列表 JSON"),
                ),
                (
                    "tools_json",
                    models.JSONField(
                        blank=True,
                        help_text="Function Calling 工具定义",
                        null=True,
                    ),
                ),
                (
                    "output_schema_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="结构化输出 Schema 类名",
                        max_length=64,
                    ),
                ),
                (
                    "structured_output",
                    models.BooleanField(
                        default=False, help_text="是否请求结构化输出"
                    ),
                ),
                (
                    "sub_agent_run_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="关联的 SubAgentRun ID（agent_runtime 审计）",
                        max_length=64,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "model_gateway_request",
                "verbose_name": "模型请求记录",
                "verbose_name_plural": "模型请求记录",
            },
        ),
        migrations.CreateModel(
            name="ModelAttempt",
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
                    "attempt_number",
                    models.PositiveIntegerField(
                        default=1, help_text="重试序号，从 1 开始"
                    ),
                ),
                (
                    "provider_name",
                    models.CharField(
                        help_text="实际调用的 Provider 名称", max_length=32
                    ),
                ),
                (
                    "model_name",
                    models.CharField(
                        help_text="实际使用的模型名称", max_length=64
                    ),
                ),
                (
                    "response_json",
                    models.JSONField(
                        blank=True,
                        help_text="原始响应 JSON（content + tool_calls）",
                        null=True,
                    ),
                ),
                (
                    "usage_json",
                    models.JSONField(
                        blank=True,
                        help_text="Token 用量 {prompt_tokens, completion_tokens, total_tokens}",
                        null=True,
                    ),
                ),
                (
                    "latency_ms",
                    models.IntegerField(
                        blank=True, help_text="调用耗时（毫秒）", null=True
                    ),
                ),
                (
                    "success",
                    models.BooleanField(default=False, help_text="调用是否成功"),
                ),
                (
                    "error_code",
                    models.CharField(
                        blank=True, default="", help_text="错误码", max_length=64
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, default="", help_text="错误详情"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "request",
                    models.ForeignKey(
                        help_text="关联的请求记录",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="model_gateway.modelrequest",
                    ),
                ),
            ],
            options={
                "db_table": "model_gateway_attempt",
                "verbose_name": "模型调用记录",
                "verbose_name_plural": "模型调用记录",
            },
        ),
        migrations.AddIndex(
            model_name="modelrequest",
            index=models.Index(
                fields=["task_type", "created_at"],
                name="mgw_request_task_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="modelattempt",
            index=models.Index(
                fields=["request", "attempt_number"],
                name="mgw_attempt_req_num_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="modelattempt",
            index=models.Index(
                fields=["success", "created_at"],
                name="mgw_attempt_success_created_idx",
            ),
        ),
    ]
