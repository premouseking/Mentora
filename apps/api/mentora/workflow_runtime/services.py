"""
WorkflowRuntime：工作流状态机服务层。

约定：
- 纯 Django ORM 封装，不依赖 agent_runtime
- claim_next 使用 select_for_update 防止多 worker 竞态
- 租约过期后 recover_stalled 将 workflow 重置为 pending

@module mentora/workflow_runtime/services
"""

from datetime import datetime, timedelta, timezone

from django.db import transaction
from django.db.models import Q

from mentora.workflow_runtime.models import WorkflowLease, WorkflowState


class WorkflowRuntime:
    """工作流持久化状态机服务。"""

    def submit(
        self,
        workflow_type: str,
        input_json: dict,
        owner_id: str = "",
    ) -> WorkflowState:
        """提交新工作流，状态为 pending。"""
        return WorkflowState.objects.create(
            workflow_type=workflow_type,
            input_json=input_json,
            owner_id=owner_id,
            status="pending",
        )

    @transaction.atomic
    def claim_next(
        self,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> WorkflowState | None:
        """原子认领最早的 pending 工作流。

        使用 select_for_update(skip_locked=True) 避免多 worker 竞态。
        认领成功：状态推进到 running + 创建 WorkflowLease。
        返回 None 表示当前无待处理任务。
        """
        now = datetime.now(timezone.utc)

        wf = (
            WorkflowState.objects
            .select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("created_at")
            .first()
        )
        if wf is None:
            return None

        wf.status = "running"
        wf.started_at = now
        wf.save(update_fields=["status", "started_at"])

        WorkflowLease.objects.create(
            workflow=wf,
            worker_id=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )

        return wf

    def complete(
        self,
        workflow_id: str,
        output_json: dict | None = None,
    ) -> WorkflowState:
        """标记工作流为已完成。"""
        wf = WorkflowState.objects.get(id=workflow_id)
        wf.status = "completed"
        wf.completed_at = datetime.now(timezone.utc)
        if output_json is not None:
            wf.output_json = output_json
        wf.save(update_fields=["status", "completed_at", "output_json"])
        return wf

    def fail(
        self,
        workflow_id: str,
        error_code: str = "",
        error_message: str = "",
    ) -> WorkflowState:
        """标记工作流为失败。"""
        wf = WorkflowState.objects.get(id=workflow_id)
        wf.status = "failed"
        wf.completed_at = datetime.now(timezone.utc)
        wf.error_code = error_code
        wf.error_message = error_message
        wf.save(update_fields=["status", "completed_at", "error_code", "error_message"])
        return wf

    def checkpoint(
        self,
        workflow_id: str,
        step_index: int,
        data: dict,
    ) -> None:
        """保存检查点——更新当前步骤和检查点数据。"""
        WorkflowState.objects.filter(id=workflow_id).update(
            current_step_index=step_index,
            checkpoint_data=data,
        )

    def renew_lease(
        self,
        workflow_id: str,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> bool:
        """延长租约过期时间。返回 True 表示续约成功。"""
        now = datetime.now(timezone.utc)
        updated = WorkflowLease.objects.filter(
            workflow_id=workflow_id,
            worker_id=worker_id,
            lease_expires_at__gt=now,
        ).update(
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        return updated > 0

    @transaction.atomic
    def recover_stalled(self, timeout_seconds: int = 600) -> int:
        """恢复停滞工作流——释放过期租约，重置对应 workflow 为 pending。"""
        now = datetime.now(timezone.utc)
        expired_leases = WorkflowLease.objects.filter(
            lease_expires_at__lte=now,
        )

        # 收敛 -1 min 避免刚过期的被立即捡起
        recovery_cutoff = now - timedelta(minutes=1)

        recovered_count = 0
        for lease in expired_leases:
            updated = WorkflowState.objects.filter(
                id=lease.workflow_id,
                status="running",
                updated_at__lte=recovery_cutoff,
            ).update(
                status="pending",
                started_at=None,
                current_step_index=0,
            )
            if updated:
                recovered_count += updated

        expired_leases.delete()
        return recovered_count

    def get(self, workflow_id: str) -> WorkflowState | None:
        """按 ID 查询工作流。"""
        return WorkflowState.objects.filter(id=workflow_id).first()

    def list_by_owner(
        self,
        owner_id: str,
        limit: int = 20,
    ) -> list[WorkflowState]:
        """按用户查询工作流列表（按创建时间倒序）。"""
        return list(
            WorkflowState.objects
            .filter(owner_id=owner_id)
            .order_by("-created_at")[:limit]
        )
