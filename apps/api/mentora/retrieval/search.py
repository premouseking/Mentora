"""Async hybrid retrieval over PostgreSQL-backed projections."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db import connection, transaction
from pgvector.django import CosineDistance

from mentora.retrieval.models import ChunkProjection, EvidenceUnit


@dataclass
class SearchResult:
    """Single retrieval result."""

    evidence: Any
    score: float = 0.0
    fts_score: float = 0.0
    trgm_score: float = 0.0
    vector_score: float = 0.0
    semantic_content: str = ""
    matched_preview: str = ""
    block_evidence_count: int = 1
    source_title: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": str(self.evidence.id),
            "content": self.semantic_content or self.evidence.content,
            "content_preview": (self.semantic_content or self.evidence.content)[:200],
            "matched_preview": self.matched_preview or self.evidence.content,
            "page_number": self.evidence.page_number,
            "block_evidence_count": self.block_evidence_count,
            "source_title": self.source_title,
            "score": round(self.score, 4),
            "fts_score": round(self.fts_score, 4),
            "trgm_score": round(self.trgm_score, 4),
            "vector_score": round(self.vector_score, 4),
        }


@dataclass
class SearchResultSet:
    """Retrieval result set."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_candidates: int = 0
    elapsed_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total_candidates": self.total_candidates,
            "results": [r.to_dict() for r in self.results],
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


def _rrf(
    rankings: list[dict[str, float]],
    k: int = 60,
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Reciprocal Rank Fusion over independent recall rankings."""
    if weights is None:
        weights = [1.0] * len(rankings)

    ranked: list[dict[str, int]] = []
    for rank_dict in rankings:
        sorted_ids = sorted(rank_dict.keys(), key=lambda did: rank_dict[did], reverse=True)
        ranked.append({did: idx + 1 for idx, did in enumerate(sorted_ids)})

    fused: dict[str, float] = {}
    for rank_dict, weight in zip(ranked, weights):
        for doc_id, rank in rank_dict.items():
            fused[doc_id] = fused.get(doc_id, 0.0) + weight / (k + rank)

    return fused


def _scope_evidence(source_version_ids: list[str] | None):
    qs = EvidenceUnit.objects.all()
    if source_version_ids:
        qs = qs.filter(source_version_id__in=source_version_ids)
    return qs


def _scope_chunks(source_version_ids: list[str] | None):
    qs = ChunkProjection.objects.filter(embedding__isnull=False)
    if source_version_ids:
        qs = qs.filter(source_version_id__in=source_version_ids)
    return qs


def _recall_fts_sync(
    *,
    query: str,
    source_version_ids: list[str] | None,
    limit: int,
) -> dict[str, float]:
    search_query = SearchQuery(query, config="simple", search_type="plain")
    rows = (
        _scope_evidence(source_version_ids)
        .annotate(rank=SearchRank(SearchVector("content", config="simple"), search_query))
        .filter(rank__gt=0.0)
        .order_by("-rank")[:limit]
    )
    return {str(row.id): float(row.rank) for row in rows}


def _recall_trgm_sync(
    *,
    query: str,
    source_version_ids: list[str] | None,
    limit: int,
) -> dict[str, float]:
    rows = (
        _scope_evidence(source_version_ids)
        .annotate(similarity=TrigramSimilarity("content", query))
        .filter(similarity__gt=0.15)
        .order_by("-similarity")[:limit]
    )
    return {str(row.id): float(row.similarity) for row in rows}


def _recall_vector_sync(
    *,
    query_embedding: list[float] | None,
    source_version_ids: list[str] | None,
    limit: int,
) -> dict[str, float]:
    if not query_embedding:
        return {}

    probes = getattr(settings, "PGVECTOR_PROBES", 10)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ivfflat.probes = %s", [probes])
        rows = list(
            _scope_chunks(source_version_ids)
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:limit]
        )

    ranking: dict[str, float] = {}
    for row in rows:
        score = 1.0 / (1.0 + float(row.distance))
        for evidence_id in row.evidence_ids:
            key = str(evidence_id)
            ranking[key] = max(ranking.get(key, 0.0), score)
    return ranking


async def _recall_fts(**kwargs) -> dict[str, float]:
    return await sync_to_async(_recall_fts_sync, thread_sensitive=True)(**kwargs)


async def _recall_trgm(**kwargs) -> dict[str, float]:
    return await sync_to_async(_recall_trgm_sync, thread_sensitive=True)(**kwargs)


async def _recall_vector(**kwargs) -> dict[str, float]:
    return await sync_to_async(_recall_vector_sync, thread_sensitive=True)(**kwargs)


def _fetch_evidence_by_ids_sync(evidence_ids: list[str]) -> list[EvidenceUnit]:
    units = {str(unit.id): unit for unit in EvidenceUnit.objects.filter(id__in=evidence_ids)}
    return [units[evidence_id] for evidence_id in evidence_ids if evidence_id in units]


async def _fetch_evidence_by_ids(evidence_ids: list[str]) -> list[EvidenceUnit]:
    return await sync_to_async(_fetch_evidence_by_ids_sync, thread_sensitive=True)(evidence_ids)


async def _materialize_results(
    fused: dict[str, float],
    rankings: dict[str, dict[str, float]],
    top_k: int,
) -> list[SearchResult]:
    sorted_ids = sorted(fused.keys(), key=lambda did: fused[did], reverse=True)[:top_k]
    units = await _fetch_evidence_by_ids(sorted_ids)

    results: list[SearchResult] = []
    for unit in units:
        doc_id = str(unit.id)
        results.append(
            SearchResult(
                evidence=unit,
                score=fused[doc_id],
                fts_score=rankings.get("fts", {}).get(doc_id, 0.0),
                trgm_score=rankings.get("trgm", {}).get(doc_id, 0.0),
                vector_score=rankings.get("vector", {}).get(doc_id, 0.0),
            )
        )
    return results


def _apply_semantic_blocks(
    results: list[SearchResult],
    *,
    source_version_ids: list[str] | None = None,
) -> list[SearchResult]:
    """Expand anchor evidence into complete semantic blocks."""
    del source_version_ids
    from mentora.retrieval.semantic_blocks import expand_results_to_semantic_blocks

    return expand_results_to_semantic_blocks(results)


async def _apply_semantic_blocks_async(results: list[SearchResult]) -> list[SearchResult]:
    return await sync_to_async(_apply_semantic_blocks, thread_sensitive=True)(results)


def _empty_result(query: str, started_at: float) -> SearchResultSet:
    return SearchResultSet(query=query, elapsed_ms=(time.perf_counter() - started_at) * 1000)


async def async_search(
    query: str,
    top_k: int = 10,
    *,
    source_version_ids: list[str] | None = None,
    query_embedding: list[float] | None = None,
    fts_weight: float = 0.6,
    trgm_weight: float = 0.25,
    vector_weight: float = 0.15,
) -> SearchResultSet:
    """Run FTS, trigram, and optional vector recall concurrently."""
    started_at = time.perf_counter()
    if not query.strip():
        return _empty_result(query, started_at)

    recall_limit = max(top_k * 4, top_k)
    fts_ranking, trgm_ranking, vector_ranking = await asyncio.gather(
        _recall_fts(
            query=query,
            source_version_ids=source_version_ids,
            limit=recall_limit,
        ),
        _recall_trgm(
            query=query,
            source_version_ids=source_version_ids,
            limit=recall_limit,
        ),
        _recall_vector(
            query_embedding=query_embedding,
            source_version_ids=source_version_ids,
            limit=recall_limit,
        ),
    )
    fused = _rrf(
        [fts_ranking, trgm_ranking, vector_ranking],
        weights=[fts_weight, trgm_weight, vector_weight],
    )
    results = await _materialize_results(
        fused,
        {"fts": fts_ranking, "trgm": trgm_ranking, "vector": vector_ranking},
        top_k,
    )
    results = await _apply_semantic_blocks_async(results)
    return SearchResultSet(
        query=query,
        results=results,
        total_candidates=len(fused),
        elapsed_ms=(time.perf_counter() - started_at) * 1000,
    )
