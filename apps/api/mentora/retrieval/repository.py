"""
检索仓库 — 封装 Django ORM 查询。

约定：
- 所有查询方法返回 Django QuerySet 或列表
- 调用方负责事务边界
- 向量搜索的探测数从 settings.PGVECTOR_PROBES 读取

约束：
- 检索必须在课程当前作用域内过滤（source_version_id 白名单）
- 不在仓库中直接暴露原始 SQL

@module mentora/retrieval/repository
"""

from django.conf import settings
from django.db import connection, transaction
from django.db.models import QuerySet
from pgvector.django import CosineDistance

from mentora.retrieval.models import (
    ChunkProjection,
    EvidenceUnit,
    PageTextProjection,
    SentenceProjection,
)


# ── EvidenceUnit ──────────────────────────────────────


def get_evidence_by_ids(evidence_ids: list[str]) -> QuerySet[EvidenceUnit]:
    """按 ID 列表批量获取 EvidenceUnit。"""
    return EvidenceUnit.objects.filter(id__in=evidence_ids).order_by("page_number")


def get_evidence_by_scope(
    source_version_ids: list[str],
    page_number: int | None = None,
) -> QuerySet[EvidenceUnit]:
    """
    按课程作用域过滤 EvidenceUnit。

    约束：source_version_ids 为课程当前激活的 SourceVersion 白名单。
    """
    qs = EvidenceUnit.objects.filter(source_version_id__in=source_version_ids)
    if page_number is not None:
        qs = qs.filter(page_number=page_number)
    return qs.order_by("source_version_id", "page_number")


def get_evidence_by_ids_ordered(
    evidence_ids: list[str],
) -> list[EvidenceUnit]:
    """
    按给定 ID 顺序批量获取（保持传入顺序）。

    用于上下文快照恢复：EvidenceSnapshot → 原始内容。
    """
    units = {str(u.id): u for u in EvidenceUnit.objects.filter(id__in=evidence_ids)}
    return [units[eid] for eid in evidence_ids if eid in units]


# ── ChunkProjection ───────────────────────────────────


def get_chunks_by_scope(
    source_version_ids: list[str],
) -> QuerySet[ChunkProjection]:
    """按作用域过滤 Chunk 投影。"""
    return ChunkProjection.objects.filter(
        source_version_id__in=source_version_ids
    ).order_by("source_version_id")


def search_chunks_by_vector(
    query_embedding: list[float],
    source_version_ids: list[str],
    top_k: int = 10,
) -> QuerySet[ChunkProjection]:
    """
    pgvector 余弦相似度检索。

    约束：必须按作用域过滤；ivfflat.probes 在同一事务内 SET LOCAL 后查询。
    """
    probes = getattr(settings, "PGVECTOR_PROBES", 10)
    base_qs = ChunkProjection.objects.filter(
        source_version_id__in=source_version_ids,
        embedding__isnull=False,
    )

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ivfflat.probes = %s", [probes])
        return (
            base_qs.annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k]
        )


# ── PageTextProjection ────────────────────────────────


def get_page_text(
    source_version_id: str,
    page_number: int,
) -> PageTextProjection | None:
    """获取指定页面的文本投影。"""
    return (
        PageTextProjection.objects.filter(
            source_version_id=source_version_id,
            page_number=page_number,
        )
        .first()
    )


def search_pages_by_text(
    query: str,
    source_version_ids: list[str],
    top_k: int = 5,
) -> QuerySet[PageTextProjection]:
    """PG 全文检索页面文本。"""
    from django.contrib.postgres.search import SearchQuery, SearchRank

    search_query = SearchQuery(query, config="simple")
    return (
        PageTextProjection.objects.filter(
            source_version_id__in=source_version_ids,
        )
        .annotate(rank=SearchRank("search_vector", search_query))
        .filter(rank__gt=0.0)
        .order_by("-rank")[:top_k]
    )


# ── SentenceProjection ────────────────────────────────


def get_sentences_by_evidence(
    evidence_unit_id: str,
) -> QuerySet[SentenceProjection]:
    """获取指定 EvidenceUnit 的所有句子投影（按 position_index 排序）。"""
    return SentenceProjection.objects.filter(
        evidence_unit_id=evidence_unit_id,
    ).order_by("position_index")


def get_sentences_by_evidence_ids(
    evidence_unit_ids: list[str],
) -> QuerySet[SentenceProjection]:
    """批量获取多个 EvidenceUnit 的句子投影。"""
    return SentenceProjection.objects.filter(
        evidence_unit_id__in=evidence_unit_ids,
    ).order_by("evidence_unit_id", "position_index")


def search_sentences_by_vector(
    query_embedding: list[float],
    source_version_ids: list[str] | None = None,
    top_k: int = 30,
) -> QuerySet[SentenceProjection]:
    """
    pgvector 余弦相似度检索句子级投影。

    约束：只搜已有 embedding 的句子；作用域通过 evidence_unit_id 中转过滤。
    """
    from django.conf import settings
    from django.db import connection, transaction

    from mentora.retrieval.models import EvidenceUnit

    probes = getattr(settings, "PGVECTOR_PROBES", 10)
    qs = SentenceProjection.objects.filter(embedding__isnull=False)

    if source_version_ids:
        scope_evidence_ids = EvidenceUnit.objects.filter(
            source_version_id__in=source_version_ids,
        ).values_list("id", flat=True)
        qs = qs.filter(evidence_unit_id__in=scope_evidence_ids)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ivfflat.probes = %s", [probes])
        return (
            qs.annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:top_k]
        )


# ── EvidenceSnapshot ──────────────────────────────────


def create_snapshot(
    evidence_ids: list[str],
    scope_revision_id: str,
) -> "EvidenceSnapshot":
    """创建证据快照，冻结模型调用引用的 EvidenceUnit 集合。"""
    from mentora.retrieval.models import EvidenceSnapshot

    return EvidenceSnapshot.objects.create(
        evidence_ids=evidence_ids,
        scope_revision_id=scope_revision_id,
    )


def get_snapshot_by_id(snapshot_id: str) -> "EvidenceSnapshot | None":
    """按 ID 获取快照。"""
    from mentora.retrieval.models import EvidenceSnapshot

    return EvidenceSnapshot.objects.filter(id=snapshot_id).first()


def replace_evidence_for_version(source_version_id: str, rows: list) -> int:
    """原子替换指定版本下的全部证据（先删后插），供 knowledge 模块调用。"""
    from mentora.retrieval.models import EvidenceUnit

    EvidenceUnit.objects.filter(source_version_id=source_version_id).delete()
    EvidenceUnit.objects.bulk_create(rows)
    return len(rows)
