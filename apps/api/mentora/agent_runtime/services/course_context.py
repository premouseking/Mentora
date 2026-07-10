"""
课程 Agent 上下文构建：注入课程画像、资料 scope、学习计划与 mention。

约定：
- 只注入摘要与 ID，正文证据仍由 retrieve_evidence 按需检索
- source_version_ids 必须限定在当前课程 scope 内

@module mentora/agent_runtime/services/course_context
"""

from __future__ import annotations

from mentora.courses.models import Course
from mentora.courses.services import get_course_info, get_course_scope
from mentora.learning.models import LearningTask
from mentora.learning.services import get_active_plan, get_progress


def _truncate(text: str, limit: int = 240) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _summarize_plan(course_session_id: str) -> dict | None:
    plan = get_active_plan(course_session_id)
    if not plan:
        return None

    phases = []
    for phase in plan.get("phases", [])[:6]:
        units = []
        for unit in phase.get("units", [])[:8]:
            tasks = []
            for task in unit.get("tasks", [])[:6]:
                tasks.append({
                    "id": task.get("id"),
                    "title": task.get("title") or task.get("task_type"),
                    "task_type": task.get("task_type"),
                    "estimated_minutes": task.get("estimated_minutes"),
                })
            units.append({
                "id": unit.get("id"),
                "title": unit.get("title"),
                "position": unit.get("position"),
                "estimated_minutes": unit.get("estimated_minutes"),
                "tasks": tasks,
            })
        phases.append({
            "id": phase.get("id"),
            "title": phase.get("title"),
            "objective": _truncate(phase.get("objective", "")),
            "units": units,
        })

    return {
        "plan_id": plan.get("plan_id"),
        "revision_id": plan.get("revision_id"),
        "status": plan.get("status"),
        "phases": phases,
    }


def _summarize_current_task(task_id: str | None) -> dict | None:
    if not task_id:
        return None
    try:
        task = LearningTask.objects.select_related("unit", "unit__phase").get(id=task_id)
    except LearningTask.DoesNotExist:
        return None

    content = task.content_json if isinstance(task.content_json, dict) else {}
    return {
        "task_id": str(task.id),
        "title": task.title,
        "task_type": task.task_type,
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "unit_title": task.unit.title if task.unit else "",
        "phase_title": task.unit.phase.title if task.unit and task.unit.phase else "",
        "source_evidence_ids": content.get("source_evidence_ids") or [],
    }


def _build_mention_context(
    mentions: list | None,
    allowed_source_ids: set[str],
) -> dict:
    if not isinstance(mentions, list):
        return {"items": [], "source_version_ids": []}

    items = []
    mention_source_ids: list[str] = []
    for raw in mentions[:20]:
        if not isinstance(raw, dict):
            continue
        mention_type = str(raw.get("type") or "")
        mention_id = str(raw.get("id") or "")
        label = str(raw.get("label") or "")
        if not mention_id:
            continue

        item = {
            "type": mention_type,
            "id": mention_id,
            "label": label,
            "source": str(raw.get("source") or ""),
        }
        items.append(item)

        if mention_type == "course_file" and mention_id in allowed_source_ids:
            mention_source_ids.append(mention_id)

    return {
        "items": items,
        "source_version_ids": mention_source_ids,
    }


def build_course_agent_context(
    *,
    course_id: str,
    current_source_version_id: str | None = None,
    current_task_id: str | None = None,
    mentions: list | None = None,
) -> dict:
    """构建课程 Agent 上下文包。

    Raises:
        ValueError: 课程不存在
    """
    try:
        course = Course.objects.select_related("session").get(id=course_id)
    except Course.DoesNotExist as exc:
        raise ValueError(f"课程不存在: {course_id}") from exc

    course_info = get_course_info(course_id) or {}
    scope_ids = set(get_course_scope(course_id) or [])
    course_session_id = str(course.session_id)

    course_summary = {
        "course_id": str(course.id),
        "course_session_id": course_session_id,
        "goal": course_info.get("goal") or course.session.goal or "",
        "level": course_info.get("level") or course.session.level or "",
        "pace": course_info.get("pace") or course.session.pace or "",
        "school": course_info.get("school") or course.session.school or "",
        "title": course.session.title or _truncate(course.session.goal, 64) or "当前课程",
        "status": course_info.get("status") or course.session.status,
    }

    mention_context = _build_mention_context(mentions, scope_ids)
    source_version_ids = list(scope_ids)

    if current_source_version_id and current_source_version_id in scope_ids:
        if current_source_version_id not in source_version_ids:
            source_version_ids.append(current_source_version_id)

    for sid in mention_context.get("source_version_ids", []):
        if sid in scope_ids and sid not in source_version_ids:
            source_version_ids.append(sid)

    learning_plan = _summarize_plan(course_session_id)
    progress = get_progress(course_session_id)
    current_task = _summarize_current_task(current_task_id)

    learning_context = {
        "plan": learning_plan,
        "progress": progress,
        "current_task": current_task,
        "current_source_version_id": (
            current_source_version_id if current_source_version_id in scope_ids else None
        ),
    }

    return {
        "course_summary": course_summary,
        "source_version_ids": source_version_ids,
        "learning_context": learning_context,
        "mention_context": mention_context,
        "course_session_id": course_session_id,
    }


def format_course_context_prompt(context: dict) -> str:
    """将课程上下文格式化为 Tutor 可见的前缀文本。"""
    summary = context.get("course_summary") or {}
    learning = context.get("learning_context") or {}
    mentions = context.get("mention_context") or {}

    lines = [
        "[课程上下文]",
        f"课程：{summary.get('title') or '当前课程'}",
        f"目标：{summary.get('goal') or '未设置'}",
        f"水平：{summary.get('level') or '未设置'}",
    ]

    current_task = learning.get("current_task")
    if current_task:
        lines.append(
            f"当前任务：{current_task.get('title')}（{current_task.get('task_type')}，状态 {current_task.get('status')}）"
        )

    current_source = learning.get("current_source_version_id")
    if current_source:
        lines.append(f"当前打开资料版本：{current_source}")

    progress = learning.get("progress")
    if progress:
        lines.append(f"学习进度：{progress.get('progress_pct', 0)}%")

    mention_items = mentions.get("items") or []
    if mention_items:
        labels = [f"@{item.get('label')}" for item in mention_items if item.get("label")]
        if labels:
            lines.append(f"用户引用：{', '.join(labels)}")

    lines.append("[/课程上下文]")
    lines.append("说明：以上上下文仅供参考；普通寒暄、感谢、确认收到无需检索资料。")
    return "\n".join(lines)
