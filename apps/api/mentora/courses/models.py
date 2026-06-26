"""
课程临时会话模型：建课流程中存储收集到的信息。

约定：
- CourseCreationSession 仅用于建课临时状态，不取代完整 Course 模型
- inquiry_history 存储追问 Q&A 列表，每项含 question/answer/type
- status 追踪建课阶段：collecting → inquiring → generating_plan → completed

约束：
- 会话数据不保证长期持久化（后续可加 TTL 清理）
- extra 字段用于扩展，不在此处定义强类型

@see docs/architecture/end-to-end-implementation-plan.md §2.1
@module mentora/courses/models
"""

import uuid

from django.db import models


class SessionStatus(models.TextChoices):
    COLLECTING = "collecting", "收集基础信息中"
    INQUIRING = "inquiring", "AI 追问中"
    GENERATING_PLAN = "generating_plan", "生成方案中"
    COMPLETED = "completed", "方案已生成"
    STARTED = "started", "已开始学习"


class CourseCreationSession(models.Model):
    """建课临时会话，存储步骤 1-4 收集的全部信息。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=32,
        choices=SessionStatus.choices,
        default=SessionStatus.COLLECTING,
    )

    # 步骤 1：学习目标
    goal = models.TextField(blank=True, default="")

    # 由 PlannerAgent 生成的课程标题（步骤 5）
    title = models.CharField(max_length=128, blank=True, default="")

    # 步骤 2：当前基础 / 推进方式 / 时间分配 / 学校 / 截止日期
    level = models.CharField(max_length=64, blank=True, default="")
    pace = models.CharField(max_length=64, blank=True, default="")
    time_budget = models.CharField(max_length=64, blank=True, default="")
    school = models.CharField(max_length=128, blank=True, default="")
    deadline = models.DateField(null=True, blank=True, help_text="考试或截止日期（选填）")
    last_studied_at = models.DateTimeField(null=True, blank=True, help_text="最近一次进入学习的时间")

    # 步骤 4：追问历史 [{"question":"...","answer":"...","type":"single_choice|multi_choice|free_text"}]
    inquiry_history = models.JSONField(default=list)

    # 扩展字段（后续可存储生成的 plan、profile_candidates 等）
    extra = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses_session"
        verbose_name = "建课会话"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        goal_preview = self.goal[:40] + "…" if len(self.goal) > 40 else self.goal
        return f"Session({self.id}) {goal_preview or '空目标'}"


class Course(models.Model):
    """课程实体——建课流程完成后创建。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CourseCreationSession,
        on_delete=models.PROTECT,
        related_name="courses",
        help_text="来源建课会话",
    )
    active_profile_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="当前生效的 CourseProfileRevision ID",
    )
    active_scope_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="当前生效的 CourseKnowledgeScopeRevision ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses_course"
        verbose_name = "课程"
        verbose_name_plural = verbose_name


class CourseProfileRevision(models.Model):
    """版本化课程画像——目标/水平/主题，不可变草稿→确认→激活模式。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        CONFIRMED = "confirmed", "已确认"
        ACTIVE = "active", "生效中"
        SUPERSEDED = "superseded", "已替代"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="profile_revisions",
    )
    parent_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="上一版本修订 ID",
    )
    goal = models.TextField(blank=True, default="")
    level = models.CharField(max_length=64, blank=True, default="")
    pace = models.CharField(max_length=64, blank=True, default="")
    school = models.CharField(max_length=128, blank=True, default="")
    topics_json = models.JSONField(
        default=dict,
        help_text="PlannerAgent 输出的主题树",
    )
    plan_revision_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="关联 LearningPlanRevision ID",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    lock_version = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses_profile_revision"
        verbose_name = "画像修订"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["course", "-created_at"]),
            models.Index(fields=["status"]),
        ]


class CourseKnowledgeScopeRevision(models.Model):
    """版本化知识作用域——记录课程激活了哪些资料版本。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ACTIVE = "active", "生效中"
        SUPERSEDED = "superseded", "已替代"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="scope_revisions",
    )
    label = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="版本标签，如 v1",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses_scope_revision"
        verbose_name = "作用域修订"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["course", "-created_at"]),
        ]


class CourseScopeBinding(models.Model):
    """作用域绑定——每份资料一条，标记角色。"""

    class Role(models.TextChoices):
        PRIMARY = "primary", "主资料"
        REFERENCE = "reference", "参考资料"
        EXAM_SCOPE = "exam_scope", "考试范围"
        EXERCISE = "exercise", "练习"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        CourseKnowledgeScopeRevision,
        on_delete=models.CASCADE,
        related_name="bindings",
    )
    source_version_id = models.CharField(
        max_length=128,
        help_text="资料版本 ID",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.PRIMARY,
    )
    position = models.IntegerField(default=0)

    class Meta:
        db_table = "courses_scope_binding"
        verbose_name = "作用域绑定"
        verbose_name_plural = verbose_name
        ordering = ["revision", "position"]
