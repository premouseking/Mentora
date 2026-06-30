"""
将解析产出的 Pydantic EvidenceUnit 持久化到 retrieval ORM。

约定：
- source_version_id 使用 SourceVersion UUID 字符串，与 retrieval CharField 占位兼容
- 重复处理同一版本时先删除旧证据再写入
- 通过 retrieval.repository 间接访问 ORM，不跨模块直写

@module mentora/knowledge/services/persist_evidence
"""

from mentora.parsing.schemas import EvidenceUnit as PydanticEvidenceUnit
from mentora.retrieval.repository import replace_evidence_for_version


def persist_evidence_units(
    units: list[PydanticEvidenceUnit],
    source_version_id: str,
) -> int:
    """持久化证据单元，返回写入条数。"""
    rows = []
    for unit in units:
        bbox_json = None
        if unit.bbox is not None:
            bbox_json = {
                "x0": unit.bbox.x0,
                "y0": unit.bbox.y0,
                "x1": unit.bbox.x1,
                "y1": unit.bbox.y1,
            }
        from mentora.retrieval.models import EvidenceUnit as OrmEvidenceUnit
        rows.append(
            OrmEvidenceUnit(
                id=unit.id,
                source_version_id=source_version_id,
                bundle_id=unit.bundle_id,
                content=unit.content,
                page_number=unit.page_number,
                bbox_json=bbox_json,
                element_indices=unit.element_indices,
                token_count=unit.token_count,
                structure_type=unit.structure_type,
                artifact_ref=unit.artifact_ref,
            )
        )

    return replace_evidence_for_version(source_version_id, rows)
