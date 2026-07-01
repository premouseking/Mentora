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
    SessionStatus,
)


class CourseResolution:
    """resolve_course 返回值。"""

    __slots__ = ("course", "session", "course_id", "session_id")

    def __init__(
        self,
        *,
        course: Course | None,
        session: CourseCreationSession,
    ) -> None:
        self.course = course
        self.session = session
        self.course_id = str(course.id) if course else None
        self.session_id = str(session.id)


def resolve_course(resource_id: str) -> CourseResolution:
    """course_id 优先；否则按 session_id 解析（建课期）。"""
    try:
        course = Course.objects.select_related("session").get(id=resource_id)
        return CourseResolution(course=course, session=course.session)
    except Course.DoesNotExist:
        pass

    session = CourseCreationSession.objects.get(id=resource_id)
    course = Course.objects.filter(session=session).first()
    return CourseResolution(course=course, session=session)


def resolve_course_required(resource_id: str) -> tuple[Course, CourseCreationSession]:
    """学习期 API：必须已有正式 Course。"""
    resolved = resolve_course(resource_id)
    if resolved.course is None:
        raise ValueError(f"课程 {resource_id} 尚未创建，请先开始学习")
    return resolved.course, resolved.session


def bind_durable_course_refs(session: CourseCreationSession, course: Course) -> None:
    """将 learning / assessment / topics 从 session 键改绑到 Course FK。"""
    from mentora.assessment.models import AssessmentItem, AssessmentSession
    from mentora.learning.models import LearningPlan
    from mentora.topics.models import Topic

    session_id = str(session.id)
    course_uuid = course.id

    LearningPlan.objects.filter(creation_session=session).update(course_id=course_uuid)
    AssessmentItem.objects.filter(creation_session=session).update(course_id=course_uuid)
    AssessmentSession.objects.filter(creation_session=session).update(course_id=course_uuid)

    Topic.objects.filter(legacy_course_key=session_id).update(
        course_id=course_uuid,
        legacy_course_key=str(course_uuid),
    )
    Topic.objects.filter(course_id=course_uuid, legacy_course_key="").update(
        legacy_course_key=str(course_uuid),
    )


def archive_session(session: CourseCreationSession) -> None:
    """开始学习后归档建课会话（只读）。"""
    session.status = SessionStatus.ARCHIVED
    session.save(update_fields=["status", "updated_at"])


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
    existing = Course.objects.filter(session=session).first()
    if existing is not None:
        bind_durable_course_refs(session, existing)
        source_version_ids = get_course_scope(str(existing.id)) or session.extra.get("source_version_ids", [])
        return {
            "course_id": str(existing.id),
            "profile_revision_id": str(existing.active_profile_revision_id or ""),
            "scope_revision_id": str(existing.active_scope_revision_id or ""),
            "bindings": [
                str(binding.id)
                for binding in CourseScopeBinding.objects.filter(
                    revision_id=existing.active_scope_revision_id,
                ).order_by("position")
            ],
            "source_version_ids": source_version_ids,
        }

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

    bind_durable_course_refs(session, course)

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
        from mentora.learning.models import LearningPlanRevision
        from mentora.learning.services import activate_revision

        plan_revision = LearningPlanRevision.objects.filter(
            id=profile.plan_revision_id,
        ).first()
        if plan_revision and plan_revision.status != LearningPlanRevision.Status.ACTIVE:
            activate_revision(str(profile.plan_revision_id))

    # 写入学习记录
    from mentora.learning.services import write_history_event
    write_history_event(
        course_id=str(course.id),
        event_type="course_started",
        title=f"开始课程：{profile.goal[:50] if profile.goal else '新课程'}",
        detail="课程已激活，学习计划已就绪。",
        result="已激活",
    )

    return {
        "course_id": str(course.id),
        "profile_revision_id": str(profile.id),
        "status": profile.status,
    }


@transaction.atomic
def revise_profile(
    course_id: str,
    *,
    goal: str | None = None,
    level: str | None = None,
    pace: str | None = None,
    school: str | None = None,
    topics_json: dict | None = None,
    plan_revision_id: str | None = None,
) -> dict:
    """克隆当前生效画像为新草稿，用户确认后调用 activate_course 激活。

    继承旧画像所有字段，仅覆盖传入的非 None 参数。
    """
    course = Course.objects.get(id=course_id)
    old = CourseProfileRevision.objects.get(
        id=course.active_profile_revision_id,
    )

    # 标记旧版本 superseded
    old.status = CourseProfileRevision.Status.SUPERSEDED
    old.save(update_fields=["status"])

    new = CourseProfileRevision.objects.create(
        course=course,
        parent_revision_id=old.id,
        goal=goal if goal is not None else old.goal,
        level=level if level is not None else old.level,
        pace=pace if pace is not None else old.pace,
        school=school if school is not None else old.school,
        topics_json=topics_json if topics_json is not None else old.topics_json,
        plan_revision_id=plan_revision_id if plan_revision_id is not None
        else old.plan_revision_id,
        lock_version=old.lock_version + 1,
        status=CourseProfileRevision.Status.DRAFT,
    )

    course.active_profile_revision_id = new.id
    course.save(update_fields=["active_profile_revision_id"])

    return {
        "course_id": str(course.id),
        "superseded_revision_id": str(old.id),
        "profile_revision_id": str(new.id),
        "status": new.status,
        "goal": new.goal,
        "level": new.level,
        "pace": new.pace,
    }


def get_course_info(course_id: str) -> dict | None:
    """获取课程基本信息（画像 + 作用域），供外部模块查询。"""
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return None

    profile = None
    if course.active_profile_revision_id:
        try:
            profile = CourseProfileRevision.objects.get(
                id=course.active_profile_revision_id,
            )
        except CourseProfileRevision.DoesNotExist:
            pass

    scope = get_course_scope(course_id) or []

    return {
        "course_id": str(course.id),
        "goal": profile.goal if profile else "",
        "level": profile.level if profile else "",
        "pace": profile.pace if profile else "",
        "school": profile.school if profile else "",
        "status": profile.status if profile else "",
        "source_version_ids": scope,
    }


def suggest_scope_updates(course_id: str) -> dict:
    """检查是否有已完成解析的新资料可加入课程作用域。"""
    current_scope = get_course_scope(course_id) or []

    from mentora.knowledge.services import get_completed_source_versions
    all_completed = get_completed_source_versions()

    new_sources = [
        str(s) for s in all_completed
        if str(s) not in current_scope
    ]

    return {
        "current_scope": current_scope,
        "new_sources_available": new_sources,
        "suggested": len(new_sources) > 0,
    }
