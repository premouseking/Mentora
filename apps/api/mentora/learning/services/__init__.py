"""
学习计划领域服务：计划创建、校验、激活与查询。

约定：
- 计划激活与任务物化分离：激活失败才阻断，物化失败不 rollback 激活
- feasibility_status 由内部校验函数自动计算
- 不在此模块引入 Agent 层依赖

@module mentora/learning/services
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

from mentora.learning.models import (
    LearningPlan,
    LearningPlanPhase,
    LearningPlanRevision,
    LearningPlanTaskTemplate,
    LearningPlanUnit,
)


def _validate_revision(revision: LearningPlanRevision, snapshot: dict) -> dict:
    """校验计划可行性，返回 validation_result_json。"""
    issues: list[str] = []
    budget_minutes = snapshot.get("total_budget_minutes", 0)
    phases = snapshot.get("phases", [])

    total_estimated = sum(
        sum(unit.get("estimated_minutes", 0) for unit in phase.get("units", []))
        for phase in phases
    )

    if budget_minutes > 0 and total_estimated > budget_minutes * 1.2:
        issues.append("总时长超出预算 20%")

    unit_ids = set()
    for phase in phases:
        for unit in phase.get("units", []):
            uid = unit.get("id", "")
            if uid:
                unit_ids.add(uid)
            for prereq in unit.get("prerequisite_unit_ids", []):
                if prereq not in unit_ids:
                    issues.append(f"前置单元 {prereq} 不存在或在 {uid} 之后")

    if not phases or not any(phase.get("units") for phase in phases):
        issues.append("计划不包含任何学习单元")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


def _determine_feasibility(validation: dict) -> str:
    if validation["valid"]:
        return LearningPlanRevision.Feasibility.FEASIBLE
    return LearningPlanRevision.Feasibility.CONSTRAINED


@transaction.atomic
def create_plan_revision(
    course_session_id: str,
    plan_snapshot: dict,
    profile_revision_id: str = "",
    knowledge_scope_revision_id: str = "",
) -> dict:
    """创建新的计划修订版本，含阶段/单元/任务模板全量写入。

    参数：
        course_session_id: 关联课程会话 ID
        plan_snapshot: PlannerAgent 输出的计划 JSON
        profile_revision_id: 课程画像修订 ID
        knowledge_scope_revision_id: 知识作用域修订 ID

    返回：
        {plan_id, revision_id, phase_count, unit_count, task_count,
         feasibility_status, validation_result}
    """
    from mentora.courses.models import CourseCreationSession
    from mentora.courses.services import resolve_course

    session = CourseCreationSession.objects.get(id=course_session_id)
    plan, _ = LearningPlan.objects.get_or_create(creation_session=session)
    resolved = resolve_course(course_session_id)
    if resolved.course_id and not plan.course_id:
        plan.course_id = resolved.course_id
        plan.save(update_fields=["course_id"])

    # 旧版本 superseded
    if plan.active_revision_id:
        LearningPlanRevision.objects.filter(
            id=plan.active_revision_id,
        ).update(status=LearningPlanRevision.Status.SUPERSEDED)

    validation = _validate_revision(None, plan_snapshot)
    feasibility = _determine_feasibility(validation)

    revision = LearningPlanRevision.objects.create(
        learning_plan=plan,
        profile_revision_id=profile_revision_id,
        knowledge_scope_revision_id=knowledge_scope_revision_id,
        plan_snapshot_json=plan_snapshot,
        feasibility_status=feasibility,
        validation_result_json=validation,
        status=LearningPlanRevision.Status.DRAFT,
    )

    phase_count = 0
    unit_count = 0
    task_count = 0

    for pi, phase_data in enumerate(plan_snapshot.get("phases", [])):
        phase = LearningPlanPhase.objects.create(
            revision=revision,
            position=pi,
            title=phase_data.get("title", f"阶段 {pi+1}"),
            objective=phase_data.get("objective", ""),
            estimated_minutes=phase_data.get("estimated_minutes", 0),
        )
        phase_count += 1

        for ui, unit_data in enumerate(phase_data.get("units", [])):
            unit = LearningPlanUnit.objects.create(
                revision=revision,
                phase=phase,
                topic_id=unit_data.get("topic_id"),
                position=ui,
                target_depth=unit_data.get("target_depth", "basic"),
                estimated_minutes=unit_data.get("estimated_minutes", 0),
                prerequisite_unit_ids=unit_data.get("prerequisite_unit_ids", []),
                priority=unit_data.get("priority", 0),
            )
            unit_count += 1

            for task_data in unit_data.get("tasks", []):
                LearningPlanTaskTemplate.objects.create(
                    revision=revision,
                    unit=unit,
                    task_type=task_data.get("task_type", "lecture"),
                    delivery_mode=task_data.get("delivery_mode", "text"),
                    estimated_minutes=task_data.get("estimated_minutes", 0),
                    required=task_data.get("required", True),
                )
                task_count += 1

    return {
        "plan_id": str(plan.id),
        "revision_id": str(revision.id),
        "phase_count": phase_count,
        "unit_count": unit_count,
        "task_count": task_count,
        "feasibility_status": feasibility,
        "validation_result": validation,
    }


def _safe_materialize_tasks(revision_id: str) -> None:
    """物化失败只记日志，不影响已激活的计划。"""
    try:
        materialize_tasks(revision_id)
    except Exception:
        logger.exception("计划激活后物化任务失败 revision_id=%s", revision_id)


@transaction.atomic
def activate_revision(revision_id: str) -> dict:
    """激活指定修订版本为当前生效计划。

    约束：infeasible 计划不可激活。
    """
    revision = LearningPlanRevision.objects.get(id=revision_id)

    if revision.feasibility_status == LearningPlanRevision.Feasibility.INFEASIBLE:
        raise ValueError("不可行计划不能激活")

    if revision.status not in (
        LearningPlanRevision.Status.DRAFT,
        LearningPlanRevision.Status.READY_TO_START,
    ):
        raise ValueError(f"当前状态 {revision.status} 不可激活")

    plan = revision.learning_plan
    plan.active_revision_id = revision.id
    plan.save(update_fields=["active_revision_id"])

    revision.status = LearningPlanRevision.Status.ACTIVE
    revision.save(update_fields=["status"])

    result = {
        "plan_id": str(plan.id),
        "active_revision_id": str(revision.id),
        "status": revision.status,
    }
    # 物化与激活分事务：避免 LearningTask 写入异常 rollback 激活状态
    transaction.on_commit(lambda rid=str(revision.id): _safe_materialize_tasks(rid))
    return result


def _resolve_active_revision(plan: LearningPlan) -> LearningPlanRevision | None:
    """解析当前应展示/使用的修订版本。"""
    if plan.active_revision_id:
        revision = LearningPlanRevision.objects.filter(id=plan.active_revision_id).first()
        if revision and revision.status != LearningPlanRevision.Status.SUPERSEDED:
            return revision

    return (
        LearningPlanRevision.objects.filter(learning_plan=plan)
        .exclude(status=LearningPlanRevision.Status.SUPERSEDED)
        .order_by("-created_at")
        .first()
    )


def _heal_plan_activation(plan: LearningPlan, revision: LearningPlanRevision) -> None:
    """修复「revision 已创建但未激活」的历史脏数据。"""
    updates: list[str] = []
    if plan.active_revision_id != revision.id:
        plan.active_revision_id = revision.id
        updates.append("active_revision_id")
    if updates:
        plan.save(update_fields=updates)

    if revision.status == LearningPlanRevision.Status.DRAFT:
        revision.status = LearningPlanRevision.Status.ACTIVE
        revision.save(update_fields=["status"])


def _build_plan_payload(plan: LearningPlan, revision: LearningPlanRevision) -> dict:
    phases = list(
        revision.phases.order_by("position").values(
            "id", "position", "title", "objective", "estimated_minutes",
        )
    )
    unit_titles = {
        str(unit_id): title
        for unit_id, title in revision.units.values_list("id", "phase__title")
    }
    for phase in phases:
        units = list(
            revision.units.filter(phase_id=phase["id"])
            .order_by("position")
            .values(
                "id", "position", "topic_id", "target_depth",
                "estimated_minutes", "prerequisite_unit_ids", "priority",
            )
        )
        for unit in units:
            unit["title"] = unit_titles.get(str(unit["id"]), phase["title"])
            unit["tasks"] = list(
                revision.task_templates.filter(unit_id=unit["id"])
                .values("id", "task_type", "delivery_mode", "estimated_minutes", "required")
            )
        phase["units"] = units

    return {
        "plan_id": str(plan.id),
        "revision_id": str(revision.id),
        "status": revision.status,
        "feasibility_status": revision.feasibility_status,
        "profile_revision_id": revision.profile_revision_id,
        "phases": phases,
    }


def _get_learning_plan(resource_id: str):
    """按 course FK 优先，回退 course_session_id（建课期）。"""
    from mentora.courses.services import resolve_course

    from mentora.learning.models import LearningPlan

    resolved = resolve_course(resource_id)
    if resolved.course_id:
        plan = LearningPlan.objects.filter(course_id=resolved.course_id).first()
        if plan is not None:
            return plan
    try:
        return LearningPlan.objects.get(creation_session_id=resolved.session_id)
    except LearningPlan.DoesNotExist:
        return None


def get_active_plan(resource_id: str) -> dict | None:
    """获取课程当前生效的学习计划（resource_id 为 course_id 或 session_id）。"""
    plan = _get_learning_plan(resource_id)
    if plan is None:
        return None

    revision = _resolve_active_revision(plan)
    if revision is None:
        return None

    if not plan.active_revision_id or plan.active_revision_id != revision.id:
        _heal_plan_activation(plan, revision)

    return _build_plan_payload(plan, revision)


def get_progress(resource_id: str) -> dict | None:
    """
    获取学习进度摘要。

    通过 assessment.services 判断 unit 完成状态。
    """
    from mentora.assessment.services import get_latest_session_for_unit

    plan = get_active_plan(resource_id)
    if not plan:
        return None

    total_minutes = 0
    completed_minutes = 0
    phase_summaries = []

    for phase in plan["phases"]:
        p_total = 0
        p_completed = 0
        unit_summaries = []

        for unit in phase["units"]:
            unit_minutes = unit["estimated_minutes"]
            session = get_latest_session_for_unit(unit["id"])

            unit_completed = session is not None and session["score_pct"] >= 60
            unit_score = session["score_pct"] if session else None

            unit_summaries.append({
                "unit_id": unit["id"],
                "title": unit.get("title", ""),
                "position": unit["position"],
                "target_depth": unit["target_depth"],
                "estimated_minutes": unit_minutes,
                "completed": unit_completed,
                "score_pct": unit_score,
                "task_count": len(unit["tasks"]),
            })

            p_total += unit_minutes
            if unit_completed:
                p_completed += unit_minutes

        total_minutes += p_total
        completed_minutes += p_completed

        phase_summaries.append({
            "phase_id": phase["id"],
            "title": phase["title"],
            "estimated_minutes": p_total,
            "completed": p_total > 0 and p_completed == p_total,
            "units": unit_summaries,
        })

    return {
        "plan_id": plan["plan_id"],
        "total_estimated_minutes": total_minutes,
        "completed_minutes": completed_minutes,
        "progress_pct": round(completed_minutes / max(total_minutes, 1) * 100),
        "phases": phase_summaries,
    }


def materialize_tasks(revision_id: str, *, weeks: int = 2) -> dict:
    """
    从 TaskTemplate 物化未来 N 周的可执行 LearningTask。

    按 estimated_minutes 分配日期——每天最多 120min。
    已有同模板任务的跳过（幂等）。
    """
    from datetime import datetime, timedelta, timezone

    from mentora.learning.models import (
        LearningPlanRevision,
        LearningPlanTaskTemplate,
        LearningTask,
    )

    revision = LearningPlanRevision.objects.get(id=revision_id)
    templates = list(
        LearningPlanTaskTemplate.objects.filter(revision=revision)
        .select_related("unit", "unit__phase")
        .order_by("unit__phase__position", "unit__position", "id")
    )

    if not templates:
        return {"task_count": 0, "message": "无任务模板"}

    existing_ids = set(
        LearningTask.objects.filter(
            revision=revision, template__isnull=False,
        ).values_list("template_id", flat=True)
    )

    now = datetime.now(timezone.utc)
    current_date = now
    daily_minutes = 0
    task_count = 0

    for tmpl in templates:
        if tmpl.id in existing_ids:
            continue

        if daily_minutes + tmpl.estimated_minutes > 120:
            current_date = current_date + timedelta(days=1)
            daily_minutes = 0

        cutoff = now + timedelta(weeks=weeks * 7)

        unit_label = tmpl.unit.phase.title if tmpl.unit.phase else f"第 {tmpl.unit.position + 1} 章"
        LearningTask.objects.create(
            revision=revision,
            unit=tmpl.unit,
            template=tmpl,
            title=f"{tmpl.get_task_type_display()}: {unit_label}",
            task_type=tmpl.task_type,
            estimated_minutes=tmpl.estimated_minutes,
            required=tmpl.required,
            position=tmpl.unit.position,
            due_date=current_date if current_date <= cutoff else None,
        )
        daily_minutes += tmpl.estimated_minutes
        task_count += 1

    return {"task_count": task_count}


def _resolve_plan_session_id(resource_id: str) -> str:
    """deprecated：请使用 courses.services.resolve_course。"""
    from mentora.courses.services import resolve_course

    return resolve_course(resource_id).session_id


def get_upcoming_tasks(course_id: str, *, limit: int = 20) -> list[dict]:
    """查询课程下所有待办任务。"""
    from mentora.courses.services import resolve_course

    from mentora.learning.models import LearningTask

    resolved = resolve_course(course_id)
    if resolved.course_id:
        tasks = LearningTask.objects.filter(
            revision__learning_plan__course_id=resolved.course_id,
            status__in=("pending", "in_progress"),
        ).order_by("due_date", "position")[:limit]
    else:
        tasks = LearningTask.objects.filter(
            revision__learning_plan__creation_session_id=resolved.session_id,
            status__in=("pending", "in_progress"),
        ).order_by("due_date", "position")[:limit]

    return [
        {
            "task_id": str(t.id),
            "title": t.title,
            "task_type": t.task_type,
            "status": t.status,
            "unit_id": str(t.unit_id),
            "estimated_minutes": t.estimated_minutes,
            "required": t.required,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks
    ]


def complete_task(task_id: str) -> dict:
    """标记任务完成。"""
    from django.utils import timezone

    from mentora.learning.models import LearningTask

    task = LearningTask.objects.get(id=task_id)
    task.status = LearningTask.Status.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "completed_at"])

    # 写入学习记录
    try:
        plan = task.unit.revision.learning_plan
        course_id = str(plan.course_id) if plan.course_id else str(plan.creation_session_id)
    except Exception:
        course_id = ""
    write_history_event(
        course_id=course_id,
        event_type="task_completed",
        title=f"完成任务：{task.title}",
        detail="学习任务已完成。",
        result="已完成",
        task_id=str(task.id),
    )

    return {
        "task_id": str(task.id),
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def write_history_event(
    course_id: str,
    event_type: str,
    title: str,
    *,
    detail: str = "",
    result: str = "",
    task_id: str = "",
    phase_id: str = "",
) -> dict:
    """写入一条学习记录事件。"""
    from mentora.learning.models import LearningHistoryEvent

    event = LearningHistoryEvent.objects.create(
        course_id=course_id,
        event_type=event_type,
        title=title,
        detail=detail,
        result=result,
        task_id=task_id,
        phase_id=phase_id,
    )
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "title": event.title,
        "created_at": event.created_at.isoformat(),
    }


def get_history(course_id: str, *, limit: int = 50) -> list[dict]:
    """获取课程学习记录，按时间倒序。"""
    from mentora.learning.models import LearningHistoryEvent

    events = LearningHistoryEvent.objects.filter(
        course_id=course_id,
    ).order_by("-created_at")[:limit]

    return [
        {
            "id": str(e.id),
            "type": e.event_type,
            "date": e.created_at.strftime("%Y-%m-%d"),
            "time": e.created_at.strftime("%H:%M"),
            "courseId": e.course_id,
            "title": e.title,
            "detail": e.detail,
            "result": e.result,
            "taskId": e.task_id,
            "phaseId": e.phase_id,
        }
        for e in events
    ]
