"""学习任务参考资料（EvidenceUnit）解析与序列化。"""

from __future__ import annotations

import uuid

from mentora.learning.models import LearningPlanRevision, LearningPlanTaskTemplate, LearningTask


def filter_valid_uuid_strings(raw_ids: list[str] | set[str]) -> list[str]:
    """仅保留可写入 UUIDField 的 ID，避免 ORM filter 抛出 ValidationError。"""
    valid: list[str] = []
    for value in raw_ids:
        text = str(value).strip()
        if not text:
            continue
        try:
            uuid.UUID(text)
        except (ValueError, AttributeError, TypeError):
            continue
        valid.append(text)
    return valid


def normalize_evidence_ids(raw_ids: list | None) -> list[str]:
    if not raw_ids:
        return []
    return [str(eid).strip() for eid in raw_ids if str(eid).strip()]


def get_task_evidence_ids_from_snapshot(
    revision: LearningPlanRevision,
    template: LearningPlanTaskTemplate,
) -> list[str]:
    """从 plan_snapshot 按 phase/unit/task 位置读取 source_evidence_ids。"""
    snapshot = revision.plan_snapshot_json or {}
    phases = snapshot.get("phases") or []
    try:
        unit_data = phases[template.unit.phase.position]["units"][template.unit.position]
        task_data = unit_data["tasks"][template.position]
        task_ids = normalize_evidence_ids(task_data.get("source_evidence_ids"))
        if task_ids:
            return task_ids
        return normalize_evidence_ids(unit_data.get("source_evidence_ids"))
    except (IndexError, KeyError, TypeError, AttributeError):
        return []


def get_learning_task_source_evidence_ids(task: LearningTask) -> list[str]:
    content = task.content_json or {}
    ids = normalize_evidence_ids(content.get("source_evidence_ids"))
    if ids:
        return ids
    if task.template_id and task.revision_id:
        try:
            template = task.template
            if template is not None:
                return get_task_evidence_ids_from_snapshot(task.revision, template)
        except LearningPlanTaskTemplate.DoesNotExist:
            pass
    return []


def build_task_sources(evidence_ids: list[str]) -> list[dict]:
    """构建任务详情 sources[]，含 source_version_id、标题、页码与 snippet。"""
    from mentora.knowledge.models import SourceVersion
    from mentora.retrieval.models import EvidenceUnit

    normalized = normalize_evidence_ids(evidence_ids)
    if not normalized:
        return []

    queryable_evidence_ids = filter_valid_uuid_strings(normalized)
    units = list(
        EvidenceUnit.objects.filter(id__in=queryable_evidence_ids).only(
            "id", "source_version_id", "page_number", "content",
        )
    )
    unit_by_id = {str(unit.id): unit for unit in units}
    version_ids = filter_valid_uuid_strings(
        {str(unit.source_version_id) for unit in units}
    )

    titles: dict[str, str] = {}
    if version_ids:
        for version in SourceVersion.objects.select_related("source").filter(id__in=version_ids):
            titles[str(version.id)] = (
                version.source.display_title
                or version.original_filename
                or f"资料 {str(version.id)[:8]}"
            )

    sources: list[dict] = []
    for evidence_id in normalized:
        unit = unit_by_id.get(evidence_id)
        if unit is None:
            continue
        snippet = (unit.content or "").strip()
        if len(snippet) > 200:
            snippet = f"{snippet[:200]}…"
        version_id = str(unit.source_version_id)
        sources.append({
            "evidence_id": str(unit.id),
            "source_version_id": version_id,
            "title": titles.get(version_id, ""),
            "page_number": unit.page_number,
            "snippet_preview": snippet,
        })
    return sources


def resolve_learning_task(task_id: str, *, owner=None) -> LearningTask | None:
    """按 LearningTask.id 或 template_id 解析可执行任务。"""
    from mentora.learning.services import ensure_learning_task_for_id

    return ensure_learning_task_for_id(task_id, owner=owner)
