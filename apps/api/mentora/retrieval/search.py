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
    semantic_content: str | None = None
    matched_preview: str | None = None
    block_evidence_count: int = 1
    source_title: str = ""

    def to_dict(self) -> dict:
        content = self.semantic_content or self.evidence.content
        matched = self.matched_preview or self.evidence.content
        return {
            "evidence_id": str(self.evidence.id),
            "content": content,
            "content_preview": content[:200],
            "matched_preview": matched[:200],
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


def _resolve_source_titles(source_version_ids: list[str] | None) -> dict[str, str]:
    if not source_version_ids:
        return {}
    try:
        from mentora.courses.scope_planning import get_source_titles

        return get_source_titles(source_version_ids)
    except Exception:
        return {}


def _apply_semantic_blocks(
    results: list[SearchResult],
    *,
    source_version_ids: list[str] | None = None,
    memory_mode: bool = False,
) -> list[SearchResult]:
    """检索后将碎片 EvidenceUnit 扩展为完整语义块。"""
    if not results:
        return results

    if memory_mode:
        from mentora.retrieval.semantic_blocks import expand_memory_results_to_semantic_blocks

        return expand_memory_results_to_semantic_blocks(results)

    from mentora.retrieval.semantic_blocks import expand_results_to_semantic_blocks

    return expand_results_to_semantic_blocks(
        results,
        source_titles=_resolve_source_titles(source_version_ids),
    )


def search(
    query: str,
    top_k: int = 10,
    *,
    mode: str = "fts",
    fts_weight: float = 0.5,
    trgm_weight: float = 0.2,
    vector_weight: float = 0.3,
    source_version_ids: list[str] | None = None,
) -> SearchResultSet:
    """
    混合检索入口。优先 PG 原生检索，DB 不可用时回退内存版。

    mode="fts"（默认）：FTS + Trgm + Vector RRF 三路融合
    mode="grep"：PostgreSQL regex 精确匹配（数字/公式/符号）
    """
    try:
        connection.ensure_connection()
        if mode == "grep":
            return _grep_search(query, top_k, source_version_ids)
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

    # 作用域过滤子句：source_version_ids 为空时不过滤
    sv_filter = ""
    sv_params: list = []
    if source_version_ids:
        sv_filter = "AND source_version_id = ANY(%s)"
        sv_params = [source_version_ids]

    # 统计总数（作用域内）
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT count(*) FROM retrieval_evidence_unit WHERE 1=1 {sv_filter}",
            sv_params,
        )
        total = cursor.fetchone()[0]

    # ── FTS 路 ─────────────────────────────────
    fts_query_str = build_fts_query(query)
    fts_ranking: dict[str, float] = {}
    if fts_query_str:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, ts_rank(search_vector, query) AS rank
                FROM retrieval_evidence_unit,
                     plainto_tsquery('simple', %s) query
                WHERE search_vector @@ query
                {sv_filter}
                ORDER BY rank DESC
                """,
                [fts_query_str] + sv_params,
            )
            for row in cursor.fetchall():
                fts_ranking[str(row[0])] = float(row[1])

    # ── Trgm 路 ────────────────────────────────
    trgm_ranking: dict[str, float] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, similarity(content, %s) AS sim
            FROM retrieval_evidence_unit
            WHERE content %% %s
            {sv_filter}
            ORDER BY sim DESC
            LIMIT 50
            """,
            [query, query] + sv_params,
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

    # 按 RRF 分数排序，取候选
    sorted_ids = sorted(fused.keys(), key=lambda did: fused[did], reverse=True)

    # ── Reranker ────────────────────────────────
    from mentora.retrieval.reranker import get_reranker

    reranker = get_reranker()
    if reranker is not None and len(sorted_ids) > top_k:
        rerank_count = min(len(sorted_ids), top_k * 3)
        candidate_ids = sorted_ids[:rerank_count]
        # 获取候选原文
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, content, page_number
                FROM retrieval_evidence_unit
                WHERE id::text = ANY(%s)
                """,
                [candidate_ids],
            )
            candidate_map = {
                str(r[0]): _make_evidence(str(r[0]), r[1], r[2])
                for r in cursor.fetchall()
            }
        candidate_docs = [
            candidate_map[did].content
            for did in candidate_ids
            if did in candidate_map
        ]
        try:
            reranked = reranker.rerank(query, candidate_docs, top_k)
            sorted_ids = [
                candidate_ids[item["index"]]
                for item in reranked
                if item["index"] < len(candidate_ids)
            ][:top_k]
        except Exception:
            # reranker 不可用时降级为 RRF 原始排序
            sorted_ids = sorted_ids[:top_k]
    else:
        sorted_ids = sorted_ids[:top_k]

    # 拿到数据对象
    from dataclasses import dataclass as _dc

    @_dc
    class _PgEvidence:
        id: str = ""
        content: str = ""
        page_number: int = 0

    def _make_evidence(eid: str, content: str = "", page: int = 0) -> _PgEvidence:
        return _PgEvidence(id=eid, content=content, page_number=page)

    id_to_unit: dict[str, _PgEvidence] = {}
    if sorted_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, content, page_number
                FROM retrieval_evidence_unit
                WHERE id::text = ANY(%s)
                """,
                [sorted_ids],
            )
            for row in cursor.fetchall():
                unit = _PgEvidence(id=str(row[0]), content=row[1], page_number=row[2])
                id_to_unit[str(unit.id)] = unit

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

    results = _apply_semantic_blocks(results, source_version_ids=source_version_ids)

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

    句子级语义搜索 → max 聚合到 EvidenceUnit。
    Chunk 粒度太粗、分数均摊不合理，改为搜 SentenceProjection，
    每个 Evidence 取其内部最高句子分（最能代表该证据与查询的相关性）。
    """
    try:
        from django.conf import settings

        from mentora.retrieval.embedding_provider import get_provider
        from mentora.retrieval.models import EvidenceUnit, SentenceProjection
        from mentora.retrieval.repository import search_sentences_by_vector

        if not getattr(settings, "EMBEDDING_DOUBAO_API_KEY", ""):
            return {}

        provider = get_provider()
        query_embedding = provider.embed([query])[0]
        sv_ids = source_version_ids or []

        sentences = list(
            search_sentences_by_vector(query_embedding, sv_ids, top_k=30)
        )
        if sentences:
            ranking: dict[str, float] = {}
            for s in sentences:
                score = 1.0 / (1.0 + float(s.distance))
                eid_str = str(s.evidence_unit_id)
                # 取最佳句子分代表该 Evidence 的相关性
                ranking[eid_str] = max(ranking.get(eid_str, 0.0), score)
            return ranking

        # 无 embedding → 补齐首批句子 embedding 后重搜
        missing_qs = SentenceProjection.objects.filter(embedding__isnull=True)
        if sv_ids:
            scope_eids = EvidenceUnit.objects.filter(
                source_version_id__in=sv_ids,
            ).values_list("id", flat=True)
            missing_qs = missing_qs.filter(evidence_unit_id__in=scope_eids)
        missing = list(missing_qs[:20])
        if not missing:
            return {}

        texts = [s.content for s in missing]
        embeddings = provider.embed(texts)
        for sent, emb in zip(missing, embeddings):
            sent.embedding = emb
        SentenceProjection.objects.bulk_update(missing, ["embedding"])

        # 重搜
        sentences = list(
            search_sentences_by_vector(query_embedding, sv_ids, top_k=30)
        )
        if not sentences:
            return {}

        ranking: dict[str, float] = {}
        for s in sentences:
            score = 1.0 / (1.0 + float(s.distance))
            eid_str = str(s.evidence_unit_id)
            ranking[eid_str] = max(ranking.get(eid_str, 0.0), score)
        return ranking
    except Exception:
        return {}


def _search_sentence(
    query: str,
    source_version_ids: list[str] | None = None,
    top_k: int = 10,
) -> list[dict]:
    """
    句子级语义检索。

    生成 query embedding → 搜 SentenceProjection → 返回 {content, score, page, ...}。
    供 agent 精确引用时调用，不参与 RRF 融合。
    """
    try:
        from django.conf import settings

        from mentora.retrieval.embedding_provider import get_provider
        from mentora.retrieval.models import EvidenceUnit, SentenceProjection
        from mentora.retrieval.repository import search_sentences_by_vector

        if not getattr(settings, "EMBEDDING_DOUBAO_API_KEY", ""):
            return []

        provider = get_provider()
        query_embedding = provider.embed([query])[0]

        sentences = list(
            search_sentences_by_vector(query_embedding, source_version_ids, top_k)
        )
        if sentences:
            return [
                {
                    "sentence_id": str(s.id),
                    "content": s.content,
                    "evidence_unit_id": str(s.evidence_unit_id),
                    "position_index": s.position_index,
                    "score": round(1.0 / (1.0 + float(s.distance)), 4),
                }
                for s in sentences
            ]

        # 无 embedding → 补齐再搜
        missing_qs = SentenceProjection.objects.filter(embedding__isnull=True)
        if source_version_ids:
            scope_eids = EvidenceUnit.objects.filter(
                source_version_id__in=source_version_ids,
            ).values_list("id", flat=True)
            missing_qs = missing_qs.filter(evidence_unit_id__in=scope_eids)
        missing = list(missing_qs[:20])
        if not missing:
            return []

        texts = [s.content for s in missing]
        embeddings = provider.embed(texts)
        for sent, emb in zip(missing, embeddings):
            sent.embedding = emb
        SentenceProjection.objects.bulk_update(missing, ["embedding"])

        sentences = list(
            search_sentences_by_vector(query_embedding, source_version_ids, top_k)
        )
        return [
            {
                "sentence_id": str(s.id),
                "content": s.content,
                "evidence_unit_id": str(s.evidence_unit_id),
                "position_index": s.position_index,
                "score": round(1.0 / (1.0 + float(s.distance)), 4),
            }
            for s in sentences
        ]
    except Exception:
        return []


def _grep_search(
    query: str,
    top_k: int,
    source_version_ids: list[str] | None = None,
) -> SearchResultSet:
    """
    PostgreSQL regex 精确搜索，用于数字/公式/符号等 FTS 无法处理的关键词。

    `~` 运算符直接匹配原始文本，不做分词。用 similarity() 排序。
    """
    t0 = time.perf_counter()

    if not query.strip():
        return SearchResultSet(query=query, elapsed_ms=(time.perf_counter() - t0) * 1000)

    sv_filter = ""
    sv_params: list = []
    if source_version_ids:
        sv_filter = "AND source_version_id = ANY(%s)"
        sv_params = [source_version_ids]

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM retrieval_evidence_unit WHERE 1=1 {sv_filter}", sv_params)
        total = cursor.fetchone()[0]

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, content, page_number, similarity(content, %s) AS sim
            FROM retrieval_evidence_unit
            WHERE content ~ %s
            {sv_filter}
            ORDER BY sim DESC
            LIMIT %s
            """,
            [query, query] + sv_params + [top_k],
        )
        results: list[SearchResult] = []
        for row in cursor.fetchall():
            results.append(SearchResult(
                evidence=type("_PgEvidence", (), {
                    "id": str(row[0]),
                    "content": row[1],
                    "page_number": row[2],
                })(),
                score=float(row[3]),
            ))

    results = _apply_semantic_blocks(results, source_version_ids=source_version_ids)

    return SearchResultSet(
        query=query,
        results=results,
        total_candidates=total,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )


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

    results = _apply_semantic_blocks(results, memory_mode=True)

    return SearchResultSet(
        query=query,
        results=results,
        total_candidates=len(_corpus),
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
