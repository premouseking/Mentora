"""
模型网关审计模型：记录每次网关请求与实际网络调用。

约定：
- ModelRequest 记录逻辑请求（task_type, messages, tools）
- ModelAttempt 记录物理调用（provider, response, usage, latency）
- 一次 ModelRequest 可能产生多次 ModelAttempt（重试）

约束：
- messages_json 和 tools_json 用 JSONB 字段
- 审计模型不参与业务逻辑

@see docs/architecture/agent-runtime-design.md §8.2
@module mentora/model_gateway/models
"""

import uuid

from django.db import models


class ModelRequest(models.Model):
    """每次网关调用的请求记录。

    记录发送给模型前的完整请求（消息列表、工具定义、输出 Schema）。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=32, db_index=True, help_text="任务类型：tutor / planner / assessor")
    provider_name = models.CharField(max_length=32, help_text="路由到的 Provider 名称")
    messages_json = models.JSONField(help_text="发送给模型的消息列表 JSON")
    tools_json = models.JSONField(null=True, blank=True, help_text="Function Calling 工具定义")
    output_schema_name = models.CharField(max_length=64, blank=True, default="", help_text="结构化输出 Schema 类名")
    structured_output = models.BooleanField(default=False, help_text="是否请求结构化输出")
    sub_agent_run_id = models.CharField(max_length=64, blank=True, default="", help_text="关联的 SubAgentRun ID（agent_runtime 审计）")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "model_gateway_request"
        verbose_name = "模型请求记录"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["task_type", "created_at"], name="mgw_request_task_created_idx"),
        ]

    def __str__(self) -> str:
        return f"ModelRequest({self.id}) {self.task_type}"


class ModelAttempt(models.Model):
    """单次实际网络调用记录（含重试）。

    每次模型网络调用创建一条，记录响应内容、Token 用量和耗时。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        ModelRequest,
        on_delete=models.CASCADE,
        related_name="attempts",
        help_text="关联的请求记录",
    )
    attempt_number = models.PositiveIntegerField(default=1, help_text="重试序号，从 1 开始")
    provider_name = models.CharField(max_length=32, help_text="实际调用的 Provider 名称")
    model_name = models.CharField(max_length=64, help_text="实际使用的模型名称")
    response_json = models.JSONField(null=True, blank=True, help_text="原始响应 JSON（content + tool_calls）")
    usage_json = models.JSONField(null=True, blank=True, help_text="Token 用量 {prompt_tokens, completion_tokens, total_tokens}")
    latency_ms = models.IntegerField(null=True, blank=True, help_text="调用耗时（毫秒）")
    success = models.BooleanField(default=False, help_text="调用是否成功")
    error_code = models.CharField(max_length=64, blank=True, default="", help_text="错误码")
    error_message = models.TextField(blank=True, default="", help_text="错误详情")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "model_gateway_attempt"
        verbose_name = "模型调用记录"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["request", "attempt_number"], name="mgw_attempt_req_num_idx"),
            models.Index(fields=["success", "created_at"], name="mgw_att_succ_created_idx"),
        ]

    def __str__(self) -> str:
        return f"ModelAttempt({self.id}) #{self.attempt_number} {self.provider_name}"
