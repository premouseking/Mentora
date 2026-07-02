from __future__ import annotations

"""
学习计划领域服务：计划创建、校验、激活与查询。

约定：
- 计划创建与激活在一个事务内完成
- feasibility_status 由内部校验函数自动计算
- 不在此模块引入 Agent 层依赖

@module mentora/learning/services
"""

import logging
import uuid

from functools import lru_cache

from django.db import DatabaseError, connection, transaction

from mentora.learning.models import (
    LearningPlan,
    LearningPlanPhase,
    LearningPlanRevision,
    LearningPlanTaskTemplate,
    LearningPlanUnit,
    LearningTask,
)

logger = logging.getLogger(__name__)


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


def _task_defaults(task: dict, *, task_index: int, unit_id: str) -> dict:
    task_type = task.get("task_type", "lecture")
    title = str(task.get("title", "")).strip()
    return {
        "id": str(task.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"{unit_id}:{task_index}:{title or task_type}")),
        "position": int(task.get("position") or task_index),
        "title": title,
        "knowledge_point": str(task.get("knowledge_point", "")).strip(),
        "task_type": task_type,
        "delivery_mode": task.get("delivery_mode", "text"),
        "estimated_minutes": int(task.get("estimated_minutes") or 0),
        "required": bool(task.get("required", True)),
        "materials": task.get("materials", []),
        "source_evidence_ids": [
            str(eid).strip()
            for eid in (task.get("source_evidence_ids") or [])
            if str(eid).strip()
        ],
    }


@lru_cache(maxsize=8)
def _table_columns(table_name: str) -> set[str]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in description}


def _supports_structured_plan_tables() -> bool:
    try:
        unit_columns = _table_columns(LearningPlanUnit._meta.db_table)
        task_columns = _table_columns(LearningPlanTaskTemplate._meta.db_table)
    except DatabaseError:
        return False
    return {"title"}.issubset(unit_columns) and {"title", "knowledge_point", "position"}.issubset(task_columns)


def _snapshot_counts(plan_snapshot: dict) -> tuple[int, int, int]:
    phases = plan_snapshot.get("phases", [])
    phase_count = len(phases)
    unit_count = sum(len(phase.get("units", [])) for phase in phases)
    task_count = sum(
        len(unit.get("tasks", []))
        for phase in phases
        for unit in phase.get("units", [])
    )
    return phase_count, unit_count, task_count


def _build_plan_from_snapshot(plan_id: str, revision: LearningPlanRevision) -> dict:
    snapshot = revision.plan_snapshot_json or {}
    phases: list[dict] = []
    for phase_index, phase_data in enumerate(snapshot.get("phases", [])):
        phase_id = str(phase_data.get("id") or uuid.uuid5(
            uuid.NAMESPACE_URL, f"{revision.id}:phase:{phase_index}:{phase_data.get('title', '')}"
        ))
        units: list[dict] = []
        for unit_index, unit_data in enumerate(phase_data.get("units", [])):
            unit_id = str(unit_data.get("id") or uuid.uuid5(
                uuid.NAMESPACE_URL, f"{phase_id}:unit:{unit_index}:{unit_data.get('title', '')}"
            ))
            raw_tasks = unit_data.get("tasks", [])
            tasks = [_task_defaults(task, task_index=i, unit_id=unit_id) for i, task in enumerate(raw_tasks)]
            units.append({
                "id": unit_id,
                "title": unit_data.get("title") or phase_data.get("title", ""),
                "position": int(unit_data.get("position") or unit_index),
                "topic_id": unit_data.get("topic_id"),
                "target_depth": unit_data.get("target_depth", "basic"),
                "estimated_minutes": int(unit_data.get("estimated_minutes") or sum(t["estimated_minutes"] for t in tasks)),
                "prerequisite_unit_ids": unit_data.get("prerequisite_unit_ids", []),
                "priority": int(unit_data.get("priority") or 0),
                "tasks": tasks,
            })

        phases.append({
            "id": phase_id,
            "position": int(phase_data.get("position") or phase_index),
            "title": phase_data.get("title", f"阶段 {phase_index + 1}"),
            "objective": phase_data.get("objective", ""),
            "estimated_minutes": int(phase_data.get("estimated_minutes") or sum(u["estimated_minutes"] for u in units)),
            "units": units,
        })

    return {
        "plan_id": str(plan_id),
        "revision_id": str(revision.id),
        "status": revision.status,
        "feasibility_status": revision.feasibility_status,
        "profile_revision_id": revision.profile_revision_id,
        "phases": phases,
    }


def _normalize_delivery_mode(value: object) -> str:
    mode = str(value or "text").strip().lower()
    allowed = {choice.value for choice in LearningPlanTaskTemplate.DeliveryMode}
    return mode if mode in allowed else LearningPlanTaskTemplate.DeliveryMode.TEXT


def _parse_optional_topic_id(value: object) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def ensure_structured_plan_from_snapshot(revision_id: str) -> bool:
    """从 plan_snapshot 回填结构化 phase/unit/template（与快照 ID 对齐）。"""
    revision = LearningPlanRevision.objects.get(id=revision_id)
    if revision.phases.exists():
        return False

    snapshot = revision.plan_snapshot_json or {}
    if not snapshot.get("phases"):
        return False
    if not _supports_structured_plan_tables():
        return False

    built = _build_plan_from_snapshot(str(revision.learning_plan_id), revision)
    with transaction.atomic():
        for phase_data in built["phases"]:
            phase = LearningPlanPhase.objects.create(
                id=phase_data["id"],
                revision=revision,
                position=phase_data["position"],
                title=phase_data.get("title", ""),
                objective=phase_data.get("objective", ""),
                estimated_minutes=int(phase_data.get("estimated_minutes") or 0),
            )
            for unit_data in phase_data["units"]:
                unit = LearningPlanUnit.objects.create(
                    id=unit_data["id"],
                    revision=revision,
                    phase=phase,
                    topic_id=_parse_optional_topic_id(unit_data.get("topic_id")),
                    title=unit_data.get("title", ""),
                    position=int(unit_data.get("position") or 0),
                    target_depth=unit_data.get("target_depth", "basic"),
                    estimated_minutes=int(unit_data.get("estimated_minutes") or 0),
                    prerequisite_unit_ids=unit_data.get("prerequisite_unit_ids", []),
                    priority=int(unit_data.get("priority") or 0),
                )
                for task_data in unit_data["tasks"]:
                    task_type = task_data.get("task_type", "lecture")
                    title = str(task_data.get("title", "")).strip()
                    knowledge_point = str(task_data.get("knowledge_point", "")).strip()
                    if not knowledge_point and task_type in ("lecture", "project"):
                        knowledge_point = title
                    LearningPlanTaskTemplate.objects.create(
                        id=task_data["id"],
                        revision=revision,
                        unit=unit,
                        title=title,
                        knowledge_point=knowledge_point,
                        task_type=task_type,
                        delivery_mode=_normalize_delivery_mode(task_data.get("delivery_mode")),
                        position=int(task_data.get("position") or 0),
                        estimated_minutes=int(task_data.get("estimated_minutes") or 0),
                        required=bool(task_data.get("required", True)),
                    )
    logger.info("Backfilled structured plan tables for revision %s", revision_id)
    return True


def find_revision_for_snapshot_task_id(task_id: str) -> LearningPlanRevision | None:
    """在仅有快照、尚未回填结构化表的 active revision 中定位 task_id。"""
    if LearningPlanTaskTemplate.objects.filter(id=task_id).exists():
        return LearningPlanTaskTemplate.objects.select_related("revision").get(id=task_id).revision

    for revision in LearningPlanRevision.objects.filter(
        status=LearningPlanRevision.Status.ACTIVE,
    ):
        if revision.phases.exists():
            continue
        built = _build_plan_from_snapshot(str(revision.learning_plan_id), revision)
        for phase in built.get("phases", []):
            for unit in phase.get("units", []):
                for task in unit.get("tasks", []):
                    if task.get("id") == task_id:
                        return revision
    return None


@transaction.atomic
def ensure_learning_task_for_id(task_id: str) -> LearningTask | None:
    """确保 snapshot/template 任务 ID 可解析为 LearningTask（必要时回填并物化）。"""
    qs = LearningTask.objects.select_related(
        "unit", "unit__phase", "template", "template__unit", "template__unit__phase", "revision",
    )
    try:
        return qs.get(id=task_id)
    except LearningTask.DoesNotExist:
        task = qs.filter(template_id=task_id).order_by("-created_at").first()
        if task is not None:
            return task

    revision = find_revision_for_snapshot_task_id(task_id)
    if revision is None:
        return None

    ensure_structured_plan_from_snapshot(str(revision.id))
    materialized = materialize_task_from_template(task_id)
    if materialized is not None:
        return qs.get(id=materialized.id)

    try:
        return qs.get(id=task_id)
    except LearningTask.DoesNotExist:
        return qs.filter(template_id=task_id).order_by("-created_at").first()


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
    plan, _ = LearningPlan.objects.get_or_create(
        course_session_id=course_session_id,
    )

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

    if not _supports_structured_plan_tables():
        phase_count, unit_count, task_count = _snapshot_counts(plan_snapshot)
        return {
            "plan_id": str(plan.id),
            "revision_id": str(revision.id),
            "phase_count": phase_count,
            "unit_count": unit_count,
            "task_count": task_count,
            "feasibility_status": feasibility,
            "validation_result": validation,
        }

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
                title=unit_data.get("title", ""),
                position=ui,
                target_depth=unit_data.get("target_depth", "basic"),
                estimated_minutes=unit_data.get("estimated_minutes", 0),
                prerequisite_unit_ids=unit_data.get("prerequisite_unit_ids", []),
                priority=unit_data.get("priority", 0),
            )
            unit_count += 1

            for ti, task_data in enumerate(unit_data.get("tasks", [])):
                task_title = str(task_data.get("title", "")).strip()
                LearningPlanTaskTemplate.objects.create(
                    revision=revision,
                    unit=unit,
                    title=task_title,
                    knowledge_point=task_title if task_data.get("task_type", "lecture") in ("lecture", "project") else "",
                    task_type=task_data.get("task_type", "lecture"),
                    delivery_mode=task_data.get("delivery_mode", "text"),
                    position=ti,
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
        LearningPlanRevision.Status.ACTIVE,  # 幂等：已激活的允许重复调用
    ):
        raise ValueError(f"当前状态 {revision.status} 不可激活")

    plan = revision.learning_plan
    plan.active_revision_id = revision.id
    plan.save(update_fields=["active_revision_id"])

    was_already_active = revision.status == LearningPlanRevision.Status.ACTIVE

    revision.status = LearningPlanRevision.Status.ACTIVE
    revision.save(update_fields=["status"])

    if not was_already_active:
        if (
            not revision.task_templates.exists()
            and (revision.plan_snapshot_json or {}).get("phases")
            and _supports_structured_plan_tables()
        ):
            ensure_structured_plan_from_snapshot(str(revision.id))
        materialize_tasks(str(revision.id))

    return {
        "plan_id": str(plan.id),
        "active_revision_id": str(revision.id),
        "status": revision.status,
    }


def get_active_plan(course_session_id: str) -> dict | None:
    """获取课程当前生效的学习计划。"""
    from django.db.models import Prefetch

    from mentora.learning.models import (
        LearningPlan,
        LearningPlanPhase,
        LearningPlanRevision,
        LearningPlanTaskTemplate,
        LearningPlanUnit,
    )

    try:
        plan = LearningPlan.objects.get(course_session_id=course_session_id)
    except LearningPlan.DoesNotExist:
        return None

    if not plan.active_revision_id:
        return None

    try:
        revision = LearningPlanRevision.objects.prefetch_related(
            Prefetch(
                "phases",
                queryset=LearningPlanPhase.objects.order_by("position"),
            ),
            Prefetch(
                "units",
                queryset=LearningPlanUnit.objects.order_by("position"),
            ),
            Prefetch(
                "task_templates",
                queryset=LearningPlanTaskTemplate.objects.order_by("position", "id"),
            ),
        ).get(id=plan.active_revision_id)
    except LearningPlanRevision.DoesNotExist:
        return None

    if (
        not revision.phases.exists()
        and (revision.plan_snapshot_json or {}).get("phases")
        and _supports_structured_plan_tables()
    ):
        ensure_structured_plan_from_snapshot(str(revision.id))
        revision = LearningPlanRevision.objects.prefetch_related(
            Prefetch(
                "phases",
                queryset=LearningPlanPhase.objects.order_by("position"),
            ),
            Prefetch(
                "units",
                queryset=LearningPlanUnit.objects.order_by("position"),
            ),
            Prefetch(
                "task_templates",
                queryset=LearningPlanTaskTemplate.objects.order_by("position", "id"),
            ),
        ).get(id=plan.active_revision_id)

    try:
        phases = [
            {
                "id": str(phase.id),
                "position": phase.position,
                "title": phase.title,
                "objective": phase.objective,
                "estimated_minutes": phase.estimated_minutes,
            }
            for phase in revision.phases.all()
        ]
        if not phases:
            return _build_plan_from_snapshot(str(plan.id), revision)

        units_by_phase: dict[str, list[LearningPlanUnit]] = {}
        for unit in revision.units.all():
            units_by_phase.setdefault(str(unit.phase_id), []).append(unit)

        tasks_by_unit: dict[str, list[dict]] = {}
        for task in revision.task_templates.all():
            task_payload = {
                "id": str(task.id),
                "position": task.position,
                "title": task.title,
                "knowledge_point": task.knowledge_point,
                "task_type": task.task_type,
                "delivery_mode": task.delivery_mode,
                "estimated_minutes": task.estimated_minutes,
                "required": task.required,
                "materials": [],
            }
            tasks_by_unit.setdefault(str(task.unit_id), []).append(task_payload)

        for phase in phases:
            units = []
            for unit in units_by_phase.get(phase["id"], []):
                units.append({
                    "id": str(unit.id),
                    "title": unit.title or phase.get("title", ""),
                    "position": unit.position,
                    "topic_id": str(unit.topic_id) if unit.topic_id else None,
                    "target_depth": unit.target_depth,
                    "estimated_minutes": unit.estimated_minutes,
                    "prerequisite_unit_ids": unit.prerequisite_unit_ids or [],
                    "priority": unit.priority,
                    "tasks": tasks_by_unit.get(str(unit.id), []),
                })
            phase["units"] = units

        return {
            "plan_id": str(plan.id),
            "revision_id": str(revision.id),
            "status": revision.status,
            "feasibility_status": revision.feasibility_status,
            "profile_revision_id": revision.profile_revision_id,
            "phases": phases,
        }
    except DatabaseError:
        # 兼容数据库尚未执行新 migration 的情况，回退到快照读取，避免学习计划页直接 500。
        return _build_plan_from_snapshot(str(plan.id), revision)


def get_progress(course_session_id: str) -> dict | None:
    """
    获取学习进度摘要。

    通过 assessment.services 判断 unit 完成状态。
    """
    from mentora.assessment.services import get_latest_session_for_unit

    plan = get_active_plan(course_session_id)
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


def _create_learning_task_from_template(
    revision: LearningPlanRevision,
    tmpl: LearningPlanTaskTemplate,
    *,
    due_date=None,
) -> LearningTask:
    from mentora.learning.services.task_sources import get_task_evidence_ids_from_snapshot

    unit_title = tmpl.unit.title if tmpl.unit and tmpl.unit.title else (
        tmpl.unit.phase.title if tmpl.unit and tmpl.unit.phase else "未知"
    )
    task_title = tmpl.title or f"{tmpl.get_task_type_display()}: {unit_title}"
    evidence_ids = get_task_evidence_ids_from_snapshot(revision, tmpl)
    content_json = (
        {"source_evidence_ids": evidence_ids}
        if evidence_ids
        else {}
    )
    return LearningTask.objects.create(
        revision=revision,
        unit=tmpl.unit,
        template=tmpl,
        title=task_title,
        task_type=tmpl.task_type,
        estimated_minutes=tmpl.estimated_minutes,
        required=tmpl.required,
        position=tmpl.position,
        due_date=due_date,
        content_json=content_json,
    )


def materialize_task_from_template(template_id: str) -> LearningTask | None:
    """按需物化单个模板任务，避免为整门课批量触发内容生成。"""
    template = (
        LearningPlanTaskTemplate.objects.select_related("unit", "unit__phase", "revision")
        .filter(id=template_id)
        .first()
    )
    if template is None:
        return None

    existing = (
        LearningTask.objects.filter(template_id=template_id)
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing

    return _create_learning_task_from_template(template.revision, template)


def materialize_tasks(revision_id: str, *, weeks: int = 2, dispatch_content: bool = True) -> dict:
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
    if not _supports_structured_plan_tables():
        return {"task_count": 0, "message": "legacy schema without structured plan tables"}

    templates = list(
        LearningPlanTaskTemplate.objects.filter(revision=revision)
        .select_related("unit", "unit__phase")
        .order_by("unit__phase__position", "unit__position", "position", "id")
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

        _create_learning_task_from_template(
            revision,
            tmpl,
            due_date=current_date if current_date <= cutoff else None,
        )
        daily_minutes += tmpl.estimated_minutes
        task_count += 1

    if dispatch_content:
        _dispatch_content_generation(revision_id)

    return {"task_count": task_count}


def _dispatch_content_generation(revision_id: str) -> None:
    """为 revision 下的 lecture 任务异步触发内容生成。"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        from mentora.learning.models import LearningTask
        lecture_tasks = LearningTask.objects.filter(
            revision_id=revision_id,
            task_type="lecture",
            content_json__content_blocks=None,
        ) | LearningTask.objects.filter(
            revision_id=revision_id,
            task_type="lecture",
            content_json={},
        )
        count = lecture_tasks.count()
        if count == 0:
            return

        from mentora.learning.services.content import generate_task_content
        generated = 0
        for task in lecture_tasks:
            try:
                if generate_task_content(str(task.id)):
                    generated += 1
            except Exception:
                pass
        logger.info("Content generation dispatched: %d/%d tasks for revision %s",
                    generated, count, revision_id[:12])
    except Exception:
        logger.exception("Content generation dispatch failed for revision %s", revision_id[:12])


def get_upcoming_tasks(course_id: str, *, limit: int = 20) -> list[dict]:
    """查询课程下所有待办任务。"""
    from mentora.learning.models import LearningTask

    tasks = LearningTask.objects.filter(
        revision__learning_plan__course_session__courses__id=course_id,
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
    course_session_id = ""
    try:
        plan = task.unit.revision.learning_plan
        if plan and plan.course_session_id:
            course_session_id = str(plan.course_session_id)
    except Exception:
        course_session_id = ""
    course_id = resolve_course_id_for_history(course_session_id=course_session_id)
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


def resolve_course_id_for_history(
    *,
    course_id: str = "",
    course_session_id: str = "",
) -> str:
    """将 Course.id 或建课 session_id 规范化为 Course.id（无课程实体时回退 session_id）。"""
    from mentora.courses.models import Course

    raw = (course_id or course_session_id or "").strip()
    if not raw:
        return ""

    course = Course.objects.filter(id=raw).first()
    if course is not None:
        return str(course.id)

    course = Course.objects.filter(session_id=raw).first()
    if course is not None:
        return str(course.id)

    return raw


def _history_course_titles(course_ids: set[str]) -> dict[str, str]:
    """批量解析 course_id → 展示标题。"""
    if not course_ids:
        return {}

    from mentora.courses.models import Course, CourseCreationSession, CourseProfileRevision

    titles: dict[str, str] = {}
    courses = Course.objects.filter(id__in=course_ids).select_related("session")
    for course in courses:
        title = ""
        if course.active_profile_revision_id:
            profile = CourseProfileRevision.objects.filter(id=course.active_profile_revision_id).first()
            if profile and profile.goal:
                title = profile.goal[:80]
        if not title and course.session:
            title = course.session.title or course.session.goal or ""
        titles[str(course.id)] = title

    # 兼容旧数据：course_id 存的是 session_id
    session_ids = course_ids - set(titles.keys())
    if session_ids:
        sessions = CourseCreationSession.objects.filter(id__in=session_ids)
        for session in sessions:
            titles[str(session.id)] = session.title or session.goal or ""
    return titles


def _history_course_filter_ids(course_id: str) -> list[str]:
    """查询时同时匹配 Course.id 与关联 session_id（兼容历史写入）。"""
    course_id = course_id.strip()
    if not course_id:
        return []

    from mentora.courses.models import Course

    ids = {course_id}
    course = Course.objects.filter(id=course_id).first()
    if course is not None:
        ids.add(str(course.session_id))
    else:
        linked = Course.objects.filter(session_id=course_id).first()
        if linked is not None:
            ids.add(str(linked.id))
    return sorted(ids)


def write_history_event(
    course_id: str,
    event_type: str,
    title: str,
    *,
    detail: str = "",
    result: str = "",
    task_id: str = "",
    phase_id: str = "",
    course_title: str = "",
) -> dict:
    """写入一条学习记录事件。"""
    from mentora.learning.models import LearningHistoryEvent

    normalized_course_id = resolve_course_id_for_history(course_id=course_id)
    event = LearningHistoryEvent.objects.create(
        course_id=normalized_course_id,
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
        "course_id": event.course_id,
        "course_title": course_title,
        "created_at": event.created_at.isoformat(),
    }


def get_history(course_id: str = "", *, limit: int = 50) -> dict:
    """获取学习记录，按时间倒序；返回前端 HistoryEvent 契约。"""
    from mentora.learning.models import LearningHistoryEvent

    qs = LearningHistoryEvent.objects.all()
    if course_id:
        filter_ids = _history_course_filter_ids(course_id)
        qs = qs.filter(course_id__in=filter_ids)

    events = qs.order_by("-created_at")[:limit]
    title_map = _history_course_titles({e.course_id for e in events if e.course_id})

    items = [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "task_id": e.task_id or None,
            "task_title": e.title,
            "course_id": e.course_id or None,
            "course_title": title_map.get(e.course_id, ""),
            "description": e.detail,
            "metadata": {
                "result": e.result,
                "phase_id": e.phase_id,
            },
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
    return {"items": items, "total": len(items)}


def get_task_detail(task_id: str) -> dict | None:
    """获取学习任务详情，包含内容块和来源资料。

    返回前端 LearningTaskDetail 结构，可直接被 LearningTaskPage 消费。
    task_id 可为 LearningTask.id 或 LearningPlanTaskTemplate.id。
    """
    from mentora.learning.services.task_sources import (
        build_task_sources,
        get_learning_task_source_evidence_ids,
        resolve_learning_task,
    )

    task = resolve_learning_task(task_id)
    if task is None:
        return None

    content = task.content_json or {}

    # 懒生成：非练习任务内容为空时调 ContentAgent（失败时不阻断详情返回）
    if task.task_type != "exercise" and not content.get("content_blocks"):
        from mentora.learning.services.content import generate_task_content
        try:
            generate_task_content(str(task.id))
            task.refresh_from_db()
            content = task.content_json or {}
        except Exception:
            logger.exception("Lazy content generation failed for task %s", task.id)

    content_blocks = content.get("content_blocks", [])
    source_eids = get_learning_task_source_evidence_ids(task)
    sources = build_task_sources(source_eids)

    unit_title = ""
    phase_title = ""
    if task.unit:
        unit_title = task.unit.title or ""
        if task.unit.phase:
            phase_title = task.unit.phase.title or ""
            if not unit_title:
                unit_title = phase_title

    return {
        "task_id": str(task.id),
        "template_id": str(task.template_id) if task.template_id else "",
        "title": task.title,
        "task_type": task.task_type,
        "unit_title": unit_title,
        "phase_title": phase_title,
        "position": task.position,
        "estimated_minutes": task.estimated_minutes,
        "content_blocks": content_blocks,
        "sources": sources,
    }
