"""出题证据上下文加载。"""

from __future__ import annotations

MAX_CONTEXT_EVIDENCE = 18


def get_source_titles(source_version_ids: list[str]) -> dict[str, str]:
    from mentora.knowledge.models import SourceVersion

    versions = SourceVersion.objects.select_related("source").filter(id__in=source_version_ids)
    titles: dict[str, str] = {}
    for version in versions:
        titles[str(version.id)] = (
            version.source.display_title
            or version.original_filename
            or f"资料 {str(version.id)[:8]}"
        )
    return titles


def get_scoped_evidence(source_version_ids: list[str], *, evidence_ids: list[str] | None = None):
    from mentora.retrieval.models import EvidenceUnit

    if evidence_ids:
        units = list(
            EvidenceUnit.objects.filter(id__in=evidence_ids)
            .order_by("source_version_id", "page_number", "created_at")
        )
        if source_version_ids:
            allowed = set(source_version_ids)
            units = [unit for unit in units if unit.source_version_id in allowed]
        return units[:MAX_CONTEXT_EVIDENCE]

    return list(
        EvidenceUnit.objects.filter(source_version_id__in=source_version_ids)
        .order_by("source_version_id", "page_number", "created_at")[:MAX_CONTEXT_EVIDENCE]
    )
