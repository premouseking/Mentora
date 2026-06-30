"""
Workflow 运行时审计模型。

约定：
- WorkflowState 持久化工作流完整生命周期
- WorkflowLease 防止多 worker 重复执行同一任务
- 不在此处实现业务逻辑

@module mentora/workflow_runtime/models
"""

import uuid

from django.db import models


class WorkflowState(models.Model):
    """工作流状态机——每次异步编排任务的持久化记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_type = models.CharField(max_length=32, help_text="chat / pipeline / course_creation")
    status = models.CharField(
        max_length=16,
        default="pending",
        help_text="pending / running / completed / failed / cancelled",
    )
    current_step_index = models.IntegerField(default=0, help_text="Pipeline 当前步骤索引")
    input_json = models.JSONField(default=dict, help_text="输入快照")
    output_json = models.JSONField(null=True, blank=True, help_text="输出快照")
    checkpoint_data = models.JSONField(null=True, blank=True, help_text="检查点数据（崩溃恢复用）")
    owner_id = models.CharField(max_length=64, blank=True, default="", help_text="发起用户 ID")
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_runtime_state"
        indexes = [
            models.Index(fields=["owner_id", "status"], name="wrs_owner_status_idx"),
            models.Index(fields=["status", "created_at"], name="wrs_status_created_idx"),
            models.Index(fields=["workflow_type", "created_at"], name="wrs_type_created_idx"),
        ]

    def __str__(self):
        return f"WorkflowState({self.id}) {self.workflow_type}/{self.status}"


class WorkflowLease(models.Model):
    """任务租约——Celery worker 执行前获取，防止重复执行。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        WorkflowState,
        on_delete=models.CASCADE,
        related_name="leases",
    )
    worker_id = models.CharField(max_length=64, help_text="持有租约的 worker 标识")
    lease_expires_at = models.DateTimeField(help_text="租约过期时间")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflow_runtime_lease"
        indexes = [
            models.Index(fields=["lease_expires_at"], name="wrl_expires_idx"),
            models.Index(fields=["worker_id"], name="wrl_worker_idx"),
        ]

    def __str__(self):
        return f"WorkflowLease({self.id}) workflow={self.workflow_id} worker={self.worker_id}"
