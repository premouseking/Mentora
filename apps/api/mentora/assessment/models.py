"""
评估模块数据模型：题目定义、测验会话与作答记录。

约定：
- 首期最小可用：3 表覆盖出题→作答→汇总
- 后续 Phase 4 扩展 ItemProvenance / Blueprint / MasteryEvidence 等完整管线

参考：docs/architecture/end-to-end-implementation-plan.md §8
@module mentora/assessment/models
"""

import uuid

from django.db import models


class AssessmentItem(models.Model):
    """题目定义。"""

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "单选题"
        MULTI_CHOICE = "multi_choice", "多选题"
        SHORT_ANSWER = "short_answer", "简答题"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        RETIRED = "retired", "已停用"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_session_id = models.UUIDField(
        db_index=True,
        help_text="关联课程会话 ID",
    )
    topic_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="关联 knowledge topic ID",
    )
    question_type = models.CharField(
        max_length=16,
        choices=QuestionType.choices,
    )
    difficulty = models.IntegerField(
        default=3,
        help_text="难度等级 1-5",
    )
    question_text = models.TextField(help_text="题干")
    options_json = models.JSONField(
        null=True,
        blank=True,
        help_text="选项列表 [{label, text}, ...]，简答题可为空",
    )
    correct_answer = models.TextField(help_text="正确答案")
    explanation = models.TextField(
        blank=True,
        default="",
        help_text="答案解析",
    )
    source_evidence_ids = models.JSONField(
        default=list,
        help_text="题目来源证据 ID 列表（从哪些资料生成）",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assessment_item"
        verbose_name = "题目"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["course_session_id", "status"]),
            models.Index(fields=["topic_id"]),
        ]


class AssessmentSession(models.Model):
    """一次测验会话。"""

    class Status(models.TextChoices):
        CREATED = "created", "已创建"
        IN_PROGRESS = "in_progress", "进行中"
        COMPLETED = "completed", "已完成"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_session_id = models.UUIDField(db_index=True)
    unit_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="关联 learning_plan_unit ID",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )
    total_items = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    score_pct = models.IntegerField(
        default=0,
        help_text="得分百分比 0-100",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assessment_session"
        verbose_name = "测验会话"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["course_session_id", "-created_at"]),
        ]


class AssessmentAttempt(models.Model):
    """单题作答记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AssessmentSession,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    item = models.ForeignKey(
        AssessmentItem,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    position = models.IntegerField(
        default=0,
        help_text="试卷中序号 0-based",
    )
    user_answer = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(
        default=0.0,
        help_text="得分 0-1",
    )
    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="作答耗时（秒）",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assessment_attempt"
        verbose_name = "作答记录"
        verbose_name_plural = verbose_name
        ordering = ["session", "position"]
