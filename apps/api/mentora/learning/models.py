"""
学习模块数据模型：学习计划、修订版本、阶段、单元与任务模板。

约定：
- 计划以版本化修订（LearningPlanRevision）管理，支持草稿→确认→激活流程
- 首期不提前物化所有 LearningTask，plan_snapshot_json 存储完整计划快照
- feasibility_status 标记计划可行性，infeasible 不可进入 ready_to_start

参考：docs/architecture/end-to-end-implementation-plan.md §9
@module mentora/learning/models
"""

import uuid

from django.db import models


class LearningPlan(models.Model):
    """学习计划，1门课1个计划。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_session_id = models.UUIDField(
        db_index=True,
        help_text="关联的 CourseCreationSession ID。等 courses 模块补充 Course model 后迁移为 FK。",
    )
    active_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="当前生效的 LearningPlanRevision ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "learning_plan"
        verbose_name = "学习计划"
        verbose_name_plural = verbose_name


class LearningPlanRevision(models.Model):
    """版本化计划草稿，存储 PlannerAgent 输出的完整结构。"""

    class Feasibility(models.TextChoices):
        FEASIBLE = "feasible", "可行"
        CONSTRAINED = "constrained", "受限"
        INFEASIBLE = "infeasible", "不可行"

    class Status(models.TextChoices):
        GENERATING = "generating", "生成中"
        DRAFT = "draft", "草稿"
        READY_TO_START = "ready_to_start", "待启动"
        ACTIVE = "active", "生效中"
        NEEDS_REPLAN = "needs_replan", "需重规划"
        SUPERSEDED = "superseded", "已替代"
        ABANDONED = "abandoned", "已放弃"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learning_plan = models.ForeignKey(
        LearningPlan,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    parent_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="上一版本修订 ID，首次创建为 None",
    )
    profile_revision_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="课程画像修订 ID",
    )
    knowledge_scope_revision_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="知识作用域修订 ID",
    )
    plan_snapshot_json = models.JSONField(
        default=dict,
        help_text="PlannerAgent 输出的完整计划快照（阶段/单元/任务模板）",
    )
    feasibility_status = models.CharField(
        max_length=16,
        choices=Feasibility.choices,
        default=Feasibility.FEASIBLE,
    )
    validation_result_json = models.JSONField(
        null=True,
        blank=True,
        help_text="校验结果：前置依赖、时长预算、覆盖率等",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    lock_version = models.IntegerField(
        default=0,
        help_text="乐观锁版本号，每次编辑递增",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "learning_plan_revision"
        verbose_name = "计划修订"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["learning_plan", "-created_at"]),
            models.Index(fields=["status"]),
        ]


class LearningPlanPhase(models.Model):
    """学习阶段。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        LearningPlanRevision,
        on_delete=models.CASCADE,
        related_name="phases",
    )
    position = models.IntegerField(help_text="阶段序号，0-based")
    title = models.CharField(max_length=128)
    objective = models.TextField(blank=True, default="")
    estimated_minutes = models.IntegerField(default=0)

    class Meta:
        db_table = "learning_plan_phase"
        verbose_name = "学习阶段"
        verbose_name_plural = verbose_name
        ordering = ["revision", "position"]


class LearningPlanUnit(models.Model):
    """学习单元。"""

    class Depth(models.TextChoices):
        BASIC = "basic", "基础"
        REINFORCE = "reinforce", "强化"
        REVIEW = "review", "复习"
        SKIP = "skip", "跳过"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        LearningPlanRevision,
        on_delete=models.CASCADE,
        related_name="units",
    )
    phase = models.ForeignKey(
        LearningPlanPhase,
        on_delete=models.CASCADE,
        related_name="units",
    )
    topic_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="关联 knowledge topic ID",
    )
    title = models.CharField(max_length=128, blank=True, default="")
    position = models.IntegerField()
    target_depth = models.CharField(
        max_length=16,
        choices=Depth.choices,
        default=Depth.BASIC,
    )
    estimated_minutes = models.IntegerField(default=0)
    prerequisite_unit_ids = models.JSONField(
        default=list,
        help_text="前置学习单元 ID 列表",
    )
    priority = models.IntegerField(default=0)

    class Meta:
        db_table = "learning_plan_unit"
        verbose_name = "学习单元"
        verbose_name_plural = verbose_name
        ordering = ["revision", "phase", "position"]


class LearningPlanTaskTemplate(models.Model):
    """任务模板，每个 Unit 包含若干任务。"""

    class TaskType(models.TextChoices):
        LECTURE = "lecture", "讲解"
        EXERCISE = "exercise", "练习"
        PROJECT = "project", "项目"
        REVIEW = "review", "复习"

    class DeliveryMode(models.TextChoices):
        TEXT = "text", "文本"
        VIDEO = "video", "视频"
        INTERACTIVE = "interactive", "交互式"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        LearningPlanRevision,
        on_delete=models.CASCADE,
        related_name="task_templates",
    )
    unit = models.ForeignKey(
        LearningPlanUnit,
        on_delete=models.CASCADE,
        related_name="task_templates",
    )
    title = models.CharField(max_length=256, blank=True, default="")
    knowledge_point = models.CharField(max_length=256, blank=True, default="")
    task_type = models.CharField(
        max_length=16,
        choices=TaskType.choices,
    )
    delivery_mode = models.CharField(
        max_length=16,
        choices=DeliveryMode.choices,
        default=DeliveryMode.TEXT,
    )
    position = models.IntegerField(default=0)
    estimated_minutes = models.IntegerField(default=0)
    required = models.BooleanField(default=True)

    class Meta:
        db_table = "learning_plan_task_template"
        verbose_name = "任务模板"
        verbose_name_plural = verbose_name
        ordering = ["unit", "position", "id"]


class LearningTask(models.Model):
    """
    物化的可执行任务。

    约定：
    - 由 LearningPlanTaskTemplate 在计划激活后按近期窗口物化
    - 首期不提前生成整门课程所有任务，只物化未来 weeks 周
    - 设计：LearningPlanRevision 是计划结构，LearningTask 是可执行实例
    """

    class Status(models.TextChoices):
        PENDING = "pending", "待完成"
        IN_PROGRESS = "in_progress", "进行中"
        COMPLETED = "completed", "已完成"
        SKIPPED = "skipped", "已跳过"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        LearningPlanRevision,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    unit = models.ForeignKey(
        LearningPlanUnit,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    template = models.ForeignKey(
        LearningPlanTaskTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        help_text="来源模板",
    )
    title = models.CharField(max_length=256, help_text="任务标题")
    task_type = models.CharField(
        max_length=16,
        choices=LearningPlanTaskTemplate.TaskType.choices,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    position = models.IntegerField(default=0)
    estimated_minutes = models.IntegerField(default=0)
    required = models.BooleanField(default=True)
    due_date = models.DateTimeField(null=True, blank=True, help_text="建议完成日期")
    completed_at = models.DateTimeField(null=True, blank=True)
    content_json = models.JSONField(
        default=dict,
        help_text="任务内容 {content_blocks: [...], source_evidence_ids: [...]}",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "learning_task"
        verbose_name = "学习任务"
        verbose_name_plural = verbose_name
        ordering = ["revision", "due_date", "position"]
        indexes = [
            models.Index(fields=["revision", "status"]),
        ]


class LearningHistoryEvent(models.Model):
    """学习记录事件——追踪课程中的每一个关键行为。"""

    class EventType(models.TextChoices):
        TASK_COMPLETED = "task_completed", "完成学习任务"
        TASK_STARTED = "task_started", "开始学习任务"
        CHECK_PASSED = "check_passed", "通过检查点"
        CHECK_FAILED = "check_failed", "检查未通过"
        STAGE_CHANGED = "stage_changed", "阶段切换"
        PLAN_ADJUSTED = "plan_adjusted", "方案调整"
        SOURCE_ADDED = "source_added", "新增课程资料"
        SOURCE_UPDATED = "source_updated", "资料版本更新"
        QUIZ_ATTEMPTED = "quiz_attempted", "尝试测验"
        SKILL_MASTERED = "skill_mastered", "技能掌握"
        COURSE_STARTED = "course_started", "开始课程"
        COURSE_PAUSED = "course_paused", "暂停课程"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_id = models.CharField(max_length=128, db_index=True, help_text="关联课程 ID")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    title = models.CharField(max_length=512)
    detail = models.TextField(blank=True, default="")
    result = models.CharField(max_length=128, blank=True, default="")
    task_id = models.CharField(max_length=128, blank=True, default="")
    phase_id = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "learning_history_event"
        verbose_name = "学习记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course_id", "-created_at"]),
        ]
