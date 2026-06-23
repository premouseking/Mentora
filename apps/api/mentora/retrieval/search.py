"""
混合检索服务：FTS（jieba + PostgreSQL tsquery） + 模糊（pg_trgm） + 向量（pgvector，预留） → RRF 融合。

约定：
- search() 优先使用 PG 原生检索（search_pg），DB 不可用时回退内存版
- jieba 分词 + 自定义词典始终在应用层执行（tokenizer.py）
- RRF（Reciprocal Rank Fusion）融合三路排名

约束：
- 不在检索结果中暴露资料正文的全部内容
- 空查询或无效查询返回空列表

@see docs/architecture/technical-solution.md §6
@module mentora/retrieval/search
"""

import math
import time
from dataclasses import dataclass, field

from django.db import connection

from mentora.retrieval.tokenizer import build_fts_query, segment

from typing import Any


@dataclass
class SearchResult:
    """单条检索结果。evidence 可以是任意含 id/content/page_number 的对象。"""

    evidence: Any  # Pydantic EvidenceUnit | _PgEvidence | ORM model
    score: float = 0.0
    fts_score: float = 0.0
    trgm_score: float = 0.0
    vector_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "evidence_id": str(self.evidence.id),
            "content_preview": self.evidence.content[:200],
            "page_number": self.evidence.page_number,
            "score": round(self.score, 4),
            "fts_score": round(self.fts_score, 4),
            "trgm_score": round(self.trgm_score, 4),
            "vector_score": round(self.vector_score, 4),
        }


@dataclass
class SearchResultSet:
    """检索结果集。"""

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


# ── in-memory corpus (fallback when DB unavailable) ────

_corpus: list[Any] = []


def load_corpus(units: list[Any]) -> None:
    global _corpus
    _corpus = units


# ── RRF ──────────────────────────────────────────────


def _rrf(
    rankings: list[dict[str, float]],
    k: int = 60,
    weights: list[float] | None = None,
) -> dict[str, float]:
    """
    Reciprocal Rank Fusion。

    各路分数单位不同（TF 加权 vs 相似度百分比 vs 余弦距离），
    不能直接相加，改为按排名融合。
    """
    if weights is None:
        weights = [1.0] * len(rankings)

    ranked: list[dict[str, int]] = []
    for rank_dict in rankings:
        sorted_ids = sorted(rank_dict.keys(), key=lambda did: rank_dict[did], reverse=True)
        ranked.append({did: idx + 1 for idx, did in enumerate(sorted_ids)})

    fused: dict[str, float] = {}
    for rank_dict, w in zip(ranked, weights):
        for doc_id, rank in rank_dict.items():
            fused[doc_id] = fused.get(doc_id, 0.0) + w / (k + rank)

    return fused


# ── public entry point ────────────────────────────────


def search(
    query: str,
    top_k: int = 10,
    fts_weight: float = 0.5,
    trgm_weight: float = 0.2,
    vector_weight: float = 0.3,
    source_version_ids: list[str] | None = None,
) -> SearchResultSet:
    """
    混合检索入口。优先 PG 原生检索，DB 不可用时回退内存版。

    vector_weight=0 时跳过向量路（适用于未配置 API key 的场景）。
    """
    try:
        connection.ensure_connection()
        return _search_pg(
            query, top_k, fts_weight, trgm_weight, vector_weight, source_version_ids,
        )
    except (Exception, RuntimeError):
        return _search_memory(query, top_k, fts_weight, trgm_weight, vector_weight)


# ── PG-native search ─────────────────────────────────


def _search_pg(
    query: str,
    top_k: int,
    fts_weight: float,
    trgm_weight: float,
    vector_weight: float = 0.3,
    source_version_ids: list[str] | None = None,
) -> SearchResultSet:
    """
    PG FTS + pg_trgm + pgvector RRF 三路融合。

    FTS：to_tsvector('simple', content) @@ jieba tsquery → ts_rank 排序
    Trgm：similarity(content, query) → 过滤 > 阈值
    Vector：query embedding → pgvector cosine distance → Chunk → Evidence 映射
    """
    t0 = time.perf_counter()

    if not query.strip():
        return SearchResultSet(query=query, elapsed_ms=(time.perf_counter() - t0) * 1000)

    # 统计总数
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM retrieval_evidence_unit")
        total = cursor.fetchone()[0]

    # ── FTS 路 ─────────────────────────────────
    fts_query_str = build_fts_query(query)
    fts_ranking: dict[str, float] = {}
    if fts_query_str:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ts_rank(search_vector, query) AS rank
                FROM retrieval_evidence_unit,
                     plainto_tsquery('simple', %s) query
                WHERE search_vector @@ query
                ORDER BY rank DESC
                """,
                [fts_query_str],
            )
            for row in cursor.fetchall():
                fts_ranking[str(row[0])] = float(row[1])

    # ── Trgm 路 ────────────────────────────────
    trgm_ranking: dict[str, float] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, similarity(content, %s) AS sim
            FROM retrieval_evidence_unit
            WHERE content %% %s
            ORDER BY sim DESC
            LIMIT 50
            """,
            [query, query],
        )
        for row in cursor.fetchall():
            trgm_ranking[str(row[0])] = float(row[1])

    # ── Vector 路 ──────────────────────────────
    vector_ranking: dict[str, float] = {}
    if vector_weight > 0:
        vector_ranking = _search_vector(query, source_version_ids)

    # ── RRF 融合 ───────────────────────────────
    rankings = [fts_ranking, trgm_ranking]
    weights = [fts_weight, trgm_weight]
    if vector_ranking:
        rankings.append(vector_ranking)
        weights.append(vector_weight)
    fused = _rrf(rankings, weights=weights)

    # 拿到数据对象
    from dataclasses import dataclass as _dc

    @_dc
    class _PgEvidence:
        id: str = ""
        content: str = ""
        page_number: int = 0

    id_to_unit: dict[str, _PgEvidence] = {}
    if fused:
        ids = list(fused.keys())[:top_k]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, content, page_number
                FROM retrieval_evidence_unit
                WHERE id::text = ANY(%s)
                """,
                [ids],
            )
            for row in cursor.fetchall():
                unit = _PgEvidence(id=str(row[0]), content=row[1], page_number=row[2])
                id_to_unit[str(unit.id)] = unit

    # 排序 + top_k
    sorted_ids = sorted(fused.keys(), key=lambda did: fused[did], reverse=True)[:top_k]

    results: list[SearchResult] = []
    for did in sorted_ids:
        unit = id_to_unit.get(did)
        if unit is None:
            continue
        results.append(SearchResult(
            evidence=unit,
            score=fused[did],
            fts_score=fts_ranking.get(did, 0.0),
            trgm_score=trgm_ranking.get(did, 0.0),
            vector_score=vector_ranking.get(did, 0.0),
        ))

    return SearchResultSet(
        query=query,
        results=results,
        total_candidates=total,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )


def _search_vector(
    query: str,
    source_version_ids: list[str] | None = None,
) -> dict[str, float]:
    """
    pgvector 向量检索路。

    生成 query embedding → 搜 ChunkProjection → 映射回 EvidenceUnit ID。
    provider 不可用或无 API key 时返回空 dict（优雅降级）。
    """
    try:
        from django.conf import settings

        from mentora.retrieval.embedding_provider import get_provider
        from mentora.retrieval.repository import search_chunks_by_vector

        # 无 API key 时快速降级，避免 API 超时等待
        if not getattr(settings, "EMBEDDING_DOUBAO_API_KEY", ""):
            return {}

        provider = get_provider()
        query_embedding = provider.embed([query])[0]
        sv_ids = source_version_ids or []

        chunks = search_chunks_by_vector(query_embedding, sv_ids, top_k=30)
        if not chunks:
            return {}

        ranking: dict[str, float] = {}
        for chunk in chunks:
            # CosineDistance 越小越相似，转为分数（越大越好）
            score = 1.0 / (1.0 + float(chunk.distance))
            for eid in chunk.evidence_ids:
                eid_str = str(eid)
                if eid_str not in ranking or score > ranking[eid_str]:
                    ranking[eid_str] = score
        return ranking
    except Exception:
        # API key 未配置 / 网络不可用 / 无 embedding 数据 → 降级
        return {}


# ── in-memory fallback ────────────────────────────────


def _search_memory(
    query: str,
    top_k: int,
    fts_weight: float,
    trgm_weight: float,
    vector_weight: float = 0.3,
) -> SearchResultSet:
    """内存版检索（DB 不可用时的回退方案）。向量路在内存模式下跳过。"""
    t0 = time.perf_counter()

    if not query.strip() or not _corpus:
        return SearchResultSet(query=query, elapsed_ms=(time.perf_counter() - t0) * 1000)

    # FTS 路：jieba 分词 + TF 加权
    fts_words = segment(query)
    fts_ranking: dict[str, float] = {}
    for unit in _corpus:
        content_lower = unit.content.lower()
        score = 0.0
        for word in fts_words:
            count = content_lower.count(word.lower())
            if count > 0:
                score += math.log1p(count)
        if score > 0:
            fts_ranking[str(unit.id)] = score

    # Trgm 路：字符重叠率
    trgm_ranking: dict[str, float] = {}
    q_chars = set(query.lower().replace(" ", ""))
    for unit in _corpus:
        c_chars = set(unit.content.lower().replace(" ", ""))
        if q_chars:
            overlap = len(q_chars & c_chars) / len(q_chars)
            if overlap > 0.15:
                trgm_ranking[str(unit.id)] = overlap

    fused = _rrf(
        [fts_ranking, trgm_ranking],
        weights=[fts_weight, trgm_weight],
    )

    id_to_unit = {str(u.id): u for u in _corpus}
    sorted_ids = sorted(fused.keys(), key=lambda did: fused[did], reverse=True)[:top_k]

    results: list[SearchResult] = []
    for did in sorted_ids:
        unit = id_to_unit.get(did)
        if unit is None:
            continue
        results.append(SearchResult(
            evidence=unit,
            score=fused[did],
            fts_score=fts_ranking.get(did, 0.0),
            trgm_score=trgm_ranking.get(did, 0.0),
        ))

    return SearchResultSet(
        query=query,
        results=results,
        total_candidates=len(_corpus),
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
