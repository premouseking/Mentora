"""
Planner 资料范围约束：读取 session scope、构造证据上下文、覆盖检查与输出校验。

@module mentora/courses/scope_planning
"""

from __future__ import annotations

import re
from typing import Any

MAX_PLANNER_EVIDENCE = 80
EVIDENCE_PREVIEW_LEN = 220
MIN_CORPUS_CHARS = 200

_STRUCTURE_PRIORITY = {
    "heading": 0,
    "table": 1,
    "list_item": 2,
    "paragraph": 3,
    "formula": 4,
}


def get_session_source_version_ids(session) -> list[str]:
    """读取建课会话绑定的资料版本 ID；extra 为空时回查 CourseSource。"""
    extra = session.extra or {}
    raw = extra.get("source_version_ids") or []
    ids = [str(item).strip() for item in raw if str(item).strip()]
    if ids:
        return ids

    from mentora.knowledge.models import CourseSource

    return [
        str(link.source_version_id)
        for link in CourseSource.objects.filter(
            course_session_id=str(session.id),
        ).order_by("id")
    ]


def get_source_titles(source_version_ids: list[str]) -> dict[str, str]:
    from mentora.knowledge.models import SourceVersion

    versions = SourceVersion.objects.select_related("source").filter(
        id__in=source_version_ids,
    )
    titles: dict[str, str] = {}
    for version in versions:
        titles[str(version.id)] = (
            version.source.display_title
            or version.original_filename
            or f"资料 {str(version.id)[:8]}"
        )
    return titles


def get_scoped_evidence_for_planner(source_version_ids: list[str]):
    from mentora.retrieval.models import EvidenceUnit

    units = list(
        EvidenceUnit.objects.filter(source_version_id__in=source_version_ids)
        .order_by("source_version_id", "page_number", "created_at")
    )
    units.sort(
        key=lambda unit: (
            unit.source_version_id,
            unit.page_number,
            _STRUCTURE_PRIORITY.get(unit.structure_type, 9),
            str(unit.id),
        )
    )
    return units[:MAX_PLANNER_EVIDENCE]


def get_allowed_evidence_ids(source_version_ids: list[str]) -> set[str]:
    """资料范围内全部 EvidenceUnit ID，供输出校验（prompt 仍只采样前 N 条）。"""
    if not source_version_ids:
        return set()

    from mentora.retrieval.models import EvidenceUnit

    return {
        str(eid)
        for eid in EvidenceUnit.objects.filter(
            source_version_id__in=source_version_ids,
        ).values_list("id", flat=True)
    }


def build_source_scope_summary(
    source_version_ids: list[str],
    source_titles: dict[str, str],
) -> str:
    if not source_version_ids:
        return "（未选择参考资料，可按通用学习目标规划，不受资料白名单约束）"

    lines = [f"- {source_titles.get(sid, sid)}" for sid in source_version_ids]
    return "用户已选择以下资料作为唯一规划范围：\n" + "\n".join(lines)


def build_source_evidence_context(
    evidence_units,
    source_titles: dict[str, str],
) -> str:
    if not evidence_units:
        return "（所选资料暂无可引用证据片段）"

    lines: list[str] = []
    for index, unit in enumerate(evidence_units, 1):
        title = source_titles.get(unit.source_version_id, unit.source_version_id)
        preview = unit.content.strip().replace("\n", " ")
        if len(preview) > EVIDENCE_PREVIEW_LEN:
            preview = preview[:EVIDENCE_PREVIEW_LEN] + "…"
        lines.append(
            f"{index}. evidence_id={unit.id} source={title} page={unit.page_number}\n{preview}"
        )
    return "\n\n".join(lines)


def assess_scope_coverage(
    goal: str,
    evidence_units,
    source_version_ids: list[str],
) -> tuple[bool, list[dict[str, str]]]:
    """资料范围是否足以试生成；未选资料时不做严格约束。"""
    if not source_version_ids:
        return True, []

    topic = (goal or "学习目标").strip()

    if not evidence_units:
        return False, [{
            "topic": topic,
            "reason": "所选资料尚未解析出可用证据片段，无法基于资料范围生成学习计划。",
            "suggested_action": "等待资料解析完成，或补充更多相关资料。",
        }]

    corpus = "\n".join(unit.content for unit in evidence_units)
    if len(corpus.strip()) < MIN_CORPUS_CHARS:
        return False, [{
            "topic": topic,
            "reason": "所选资料可引用的正文过少，可能无法覆盖完整学习目标。",
            "suggested_action": "补充更完整的主教材或参考资料。",
        }]

    keywords = _extract_goal_keywords(goal)
    if keywords:
        corpus_lower = corpus.lower()
        hits = sum(1 for kw in keywords if kw.lower() in corpus_lower)
        if hits == 0 and len(keywords) >= 2:
            return False, [{
                "topic": topic,
                "reason": "所选资料内容与学习目标关键词匹配度较低，可能无法覆盖目标中的核心主题。",
                "suggested_action": "补充与学习目标更匹配的资料，或调整学习目标范围。",
            }]

    return True, []


def _extract_goal_keywords(goal: str) -> list[str]:
    if not goal:
        return []
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", goal)
    seen: set[str] = set()
    keywords: list[str] = []
    for part in parts:
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords[:12]


def _normalize_evidence_id(raw: object) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    if token.startswith("evidence_id="):
        token = token.split("=", 1)[1].strip()
    return token


def collect_plan_evidence_ids(plan_output: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for topic in plan_output.get("topics") or []:
        for eid in topic.get("evidence_ids") or []:
            normalized = _normalize_evidence_id(eid)
            if normalized:
                ids.add(normalized)

    for phase in plan_output.get("phases") or []:
        for unit in phase.get("units") or []:
            for eid in unit.get("source_evidence_ids") or []:
                normalized = _normalize_evidence_id(eid)
                if normalized:
                    ids.add(normalized)
            for task in unit.get("tasks") or []:
                if isinstance(task, dict):
                    for eid in task.get("source_evidence_ids") or []:
                        normalized = _normalize_evidence_id(eid)
                        if normalized:
                            ids.add(normalized)
    return ids


def _filter_evidence_id_list(raw_ids: list[Any] | None, allowed_ids: set[str]) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    for raw in raw_ids or []:
        normalized = _normalize_evidence_id(raw)
        if not normalized:
            continue
        if normalized in allowed_ids:
            if normalized not in kept:
                kept.append(normalized)
        else:
            removed.append(normalized)
    return kept, removed


def sanitize_plan_evidence_ids(
    plan_output: dict[str, Any],
    allowed_ids: set[str],
) -> list[str]:
    """剔除白名单外的 evidence 引用，返回被移除的 ID 列表。"""
    removed: list[str] = []

    for topic in plan_output.get("topics") or []:
        kept, dropped = _filter_evidence_id_list(topic.get("evidence_ids"), allowed_ids)
        topic["evidence_ids"] = kept
        removed.extend(dropped)

    for phase in plan_output.get("phases") or []:
        for unit in phase.get("units") or []:
            kept, dropped = _filter_evidence_id_list(unit.get("source_evidence_ids"), allowed_ids)
            unit["source_evidence_ids"] = kept
            removed.extend(dropped)
            for task in unit.get("tasks") or []:
                if not isinstance(task, dict):
                    continue
                kept, dropped = _filter_evidence_id_list(task.get("source_evidence_ids"), allowed_ids)
                task["source_evidence_ids"] = kept
                removed.extend(dropped)

    return sorted(set(removed))


def validate_plan_evidence_ids(
    plan_output: dict[str, Any],
    allowed_ids: set[str],
) -> list[str]:
    referenced = collect_plan_evidence_ids(plan_output)
    return sorted(referenced - allowed_ids)
