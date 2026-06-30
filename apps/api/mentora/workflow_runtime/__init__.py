"""
Workflow 持久化运行时：状态机、Celery 任务调度与租约管理。

约定：
- 不 import 领域模型（与 agent_runtime 同层）
- 通过 OrchestratorTask 驱动 agent_runtime
- Celery 任务通过 WorkflowLease 防止重复执行

约束：
- WorkflowState 是状态机的唯一真实来源
- checkpoint_data 用于 worker 崩溃恢复
- 租约过期时间必须在任务执行前检查

@see docs/architecture/agent-runtime-design.md §1.3
@module mentora/workflow_runtime
"""
