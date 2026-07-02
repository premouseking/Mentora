"""
解析后构建 Chunk / Sentence 检索投影并触发 embedding。

@module mentora/retrieval/index_builder
"""

from __future__ import annotations

from django.conf import settings

from mentora.retrieval.chunk_builder import build_chunks
from mentora.retrieval.models import ChunkProjection, EvidenceUnit, SentenceProjection
from mentora.retrieval.sentence_splitter import generate_sentence_projections


def build_retrieval_projections(source_version_id: str) -> dict[str, int]:
    """
    为指定资料版本构建 ChunkProjection 与 SentenceProjection。

    返回各投影数量，供 smoke / 回填命令使用。
    """
    units = list(
        EvidenceUnit.objects.filter(source_version_id=source_version_id).order_by(
            "page_number"
        )
    )
    if not units:
        return {"evidence": 0, "chunks": 0, "sentences": 0}

    evidence_ids = [unit.id for unit in units]
    SentenceProjection.objects.filter(evidence_unit_id__in=evidence_ids).delete()
    ChunkProjection.objects.filter(source_version_id=source_version_id).delete()

    sentence_rows: list[SentenceProjection] = []
    for unit in units:
        sentence_rows.extend(generate_sentence_projections(unit.id, unit.content))
    if sentence_rows:
        SentenceProjection.objects.bulk_create(sentence_rows)

    chunk_rows = build_chunks(units)
    for chunk in chunk_rows:
        chunk.save()

    return {
        "evidence": len(units),
        "chunks": len(chunk_rows),
        "sentences": len(sentence_rows),
    }


def enqueue_embeddings(source_version_id: str, *, sync: bool = False) -> None:
    """投递或同步执行 chunk / sentence embedding 任务。"""
    from mentora.retrieval.tasks import generate_chunk_embeddings, generate_sentence_embeddings

    if sync or getattr(settings, "RETRIEVAL_EMBED_SYNC", False):
        generate_chunk_embeddings(source_version_id)
        generate_sentence_embeddings(source_version_id)
        return

    generate_chunk_embeddings.delay(source_version_id)
    generate_sentence_embeddings.delay(source_version_id)
