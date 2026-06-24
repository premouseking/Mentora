"""
课程领域服务：建课确认、作用域管理、修订克隆与激活。

约定：
- 画像与作用域采用不可变修订模式——修改先 clone，用户确认后原子切换
- 所有写操作在一个事务内完成

@module mentora/courses/services
"""

from django.db import transaction

from mentora.courses.models import (
    Course,
    CourseCreationSession,
    CourseKnowledgeScopeRevision,
    CourseProfileRevision,
    CourseScopeBinding,
)


@transaction.atomic
def confirm_course_from_session(session_id: str) -> dict:
    """从建课会话创建正式课程。

    原子操作:
    1. 创建 Course
    2. 快照 session 字段 → CourseProfileRevision(confirmed)
    3. 创建 CourseKnowledgeScopeRevision(active)
    4. 创建 CourseScopeBinding（session.extra.source_version_ids）
    5. 写入 active 指针

    返回: {course_id, profile_revision_id, scope_revision_id, bindings}
    """
    session = CourseCreationSession.objects.get(id=session_id)

    course = Course.objects.create(session=session)

    # 画像：从 session 快照
    profile = CourseProfileRevision.objects.create(
        course=course,
        goal=session.goal,
        level=session.level,
        pace=session.pace,
        school=session.school,
        plan_revision_id=session.extra.get("plan_revision_id"),
        status=CourseProfileRevision.Status.CONFIRMED,
    )

    # 作用域 + 绑定
    scope = CourseKnowledgeScopeRevision.objects.create(
        course=course,
        label="v1",
        status=CourseKnowledgeScopeRevision.Status.ACTIVE,
    )

    source_version_ids = session.extra.get("source_version_ids", [])
    bindings = []
    for pos, sv_id in enumerate(source_version_ids):
        binding = CourseScopeBinding.objects.create(
            revision=scope,
            source_version_id=sv_id,
            role=CourseScopeBinding.Role.PRIMARY if pos == 0
            else CourseScopeBinding.Role.REFERENCE,
            position=pos,
        )
        bindings.append(str(binding.id))

    course.active_profile_revision_id = profile.id
    course.active_scope_revision_id = scope.id
    course.save(update_fields=["active_profile_revision_id", "active_scope_revision_id"])

    return {
        "course_id": str(course.id),
        "profile_revision_id": str(profile.id),
        "scope_revision_id": str(scope.id),
        "bindings": bindings,
        "source_version_ids": source_version_ids,
    }


def get_course_scope(course_id: str) -> list[str] | None:
    """获取课程当前生效的资料版本 ID 列表。"""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return None

    if not course.active_scope_revision_id:
        return None

    bindings = CourseScopeBinding.objects.filter(
        revision_id=course.active_scope_revision_id,
    ).order_by("position")

    return [b.source_version_id for b in bindings]


@transaction.atomic
def extend_scope(
    course_id: str,
    source_version_ids: list[str],
    *,
    role: str = CourseScopeBinding.Role.REFERENCE,
    label: str = "",
) -> dict:
    """扩展课程资料范围——克隆当前作用域并追加新绑定。

    旧作用域标记 superseded，新作用域写入 active 指针。
    返回: {scope_revision_id, source_version_ids, superseded_revision_id}
    """
    course = Course.objects.get(id=course_id)
    old_scope = CourseKnowledgeScopeRevision.objects.get(
        id=course.active_scope_revision_id,
    )

    # 克隆绑定
    new_scope = CourseKnowledgeScopeRevision.objects.create(
        course=course,
        label=label or f"v{old_scope.course.scope_revisions.count() + 1}",
        status=CourseKnowledgeScopeRevision.Status.ACTIVE,
    )

    existing_bindings = list(
        old_scope.bindings.order_by("position").values(
            "source_version_id", "role", "position",
        )
    )
    next_pos = len(existing_bindings)
    for b in existing_bindings:
        CourseScopeBinding.objects.create(
            revision=new_scope,
            source_version_id=b["source_version_id"],
            role=b["role"],
            position=b["position"],
        )

    # 新增绑定
    for i, sv_id in enumerate(source_version_ids):
        CourseScopeBinding.objects.create(
            revision=new_scope,
            source_version_id=sv_id,
            role=role,
            position=next_pos + i,
        )

    # 原子切换
    old_scope.status = CourseKnowledgeScopeRevision.Status.SUPERSEDED
    old_scope.save(update_fields=["status"])
    course.active_scope_revision_id = new_scope.id
    course.save(update_fields=["active_scope_revision_id"])

    all_ids = list(CourseScopeBinding.objects.filter(
        revision=new_scope,
    ).order_by("position").values_list("source_version_id", flat=True))

    return {
        "scope_revision_id": str(new_scope.id),
        "source_version_ids": all_ids,
        "superseded_revision_id": str(old_scope.id),
    }


@transaction.atomic
def activate_course(course_id: str) -> dict:
    """激活课程——profile + plan 原子切换为 active。

    LearningPlanRevision 激活委托 learning.services.activate_revision。
    """
    course = Course.objects.get(id=course_id)
    profile = CourseProfileRevision.objects.get(
        id=course.active_profile_revision_id,
    )

    if profile.status != CourseProfileRevision.Status.CONFIRMED:
        raise ValueError(f"画像状态为 {profile.status}，需先 confirm")

    profile.status = CourseProfileRevision.Status.ACTIVE
    profile.save(update_fields=["status"])

    if profile.plan_revision_id:
        from mentora.learning.services import activate_revision
        activate_revision(str(profile.plan_revision_id))

    return {
        "course_id": str(course.id),
        "profile_revision_id": str(profile.id),
        "status": profile.status,
    }
