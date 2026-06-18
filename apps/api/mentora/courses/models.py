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
    COMPLETED = "completed", "已完成"


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

    # 步骤 2：当前基础 / 推进方式 / 学校
    level = models.CharField(max_length=64, blank=True, default="")
    pace = models.CharField(max_length=64, blank=True, default="")
    school = models.CharField(max_length=128, blank=True, default="")

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
