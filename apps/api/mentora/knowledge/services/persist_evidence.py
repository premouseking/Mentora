"""
将解析产出的 Pydantic EvidenceUnit 持久化到 retrieval ORM。

约定：
- 写入时同步生成 jieba segmented_content 与 PG search_vector
- 替换版本时一并清理 Chunk / Sentence 投影

@module mentora/knowledge/services/persist_evidence
"""

import jieba
from django.contrib.postgres.search import SearchVector

from mentora.parsing.schemas import EvidenceUnit as PydanticEvidenceUnit
from mentora.retrieval.models import ChunkProjection, EvidenceUnit as OrmEvidenceUnit, SentenceProjection


def persist_evidence_units(
    units: list[PydanticEvidenceUnit],
    source_version_id: str,
) -> int:
    """持久化证据单元，返回写入条数。"""
    _clear_retrieval_projections(source_version_id)

    rows: list[OrmEvidenceUnit] = []
    for unit in units:
        bbox_json = None
        if unit.bbox is not None:
            bbox_json = {
                "x0": unit.bbox.x0,
                "y0": unit.bbox.y0,
                "x1": unit.bbox.x1,
                "y1": unit.bbox.y1,
            }
        segmented = " ".join(jieba.cut(unit.content or ""))
        rows.append(
            OrmEvidenceUnit(
                id=unit.id,
                source_version_id=source_version_id,
                bundle_id=unit.bundle_id,
                content=unit.content,
                segmented_content=segmented,
                page_number=unit.page_number,
                bbox_json=bbox_json,
                element_indices=unit.element_indices,
                token_count=unit.token_count,
                structure_type=unit.structure_type,
                artifact_ref=unit.artifact_ref,
            )
        )

    if not rows:
        return 0

    OrmEvidenceUnit.objects.bulk_create(rows)
    OrmEvidenceUnit.objects.filter(source_version_id=source_version_id).update(
        search_vector=SearchVector("segmented_content", config="simple"),
    )
    return len(rows)


def _clear_retrieval_projections(source_version_id: str) -> None:
    """删除指定版本下的证据与派生投影。"""
    evidence_ids = list(
        OrmEvidenceUnit.objects.filter(source_version_id=source_version_id).values_list(
            "id", flat=True
        )
    )
    if evidence_ids:
        SentenceProjection.objects.filter(evidence_unit_id__in=evidence_ids).delete()
    OrmEvidenceUnit.objects.filter(source_version_id=source_version_id).delete()
    ChunkProjection.objects.filter(source_version_id=source_version_id).delete()
