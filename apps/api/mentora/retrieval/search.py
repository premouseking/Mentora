"""
混合检索服务：FTS（jieba + tsquery） + 模糊（pg_trgm） + 向量（pgvector） → RRF 融合。

约定：
- 当前首版使用内存中的 EvidenceUnit 列表作为语料库
- 等 WH 交付 Evidence ORM 模型后，替换 _corpus 为 PostgreSQL 查询
- 检索结果按 RRF 分数降序排列

约束：
- 不在检索结果中暴露资料正文的全部内容
- 空查询或无效查询返回空列表

@see docs/architecture/technical-solution.md §6
@module mentora/retrieval/search
"""

import math
from dataclasses import dataclass, field

from mentora.parsing.schemas import EvidenceUnit
from mentora.retrieval.tokenizer import build_fts_query, segment


@dataclass
class SearchResult:
    """单条检索结果。"""
    evidence: EvidenceUnit
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


# ── in-memory corpus (will be replaced by PG queries) ──

_corpus: list[EvidenceUnit] = []


def load_corpus(units: list[EvidenceUnit]) -> None:
    """加载 EvidenceUnit 列表作为检索语料库。"""
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

    rankings: 每路排名是一个 {doc_id: score} 字典（原始分数，只做排序用）
    weights: 各路权重，默认等权
    """
    if weights is None:
        weights = [1.0] * len(rankings)

    # 按原始分数降序排列，得到 rank（从 1 开始）
    ranked: list[dict[str, int]] = []
    for rank_dict in rankings:
        sorted_ids = sorted(rank_dict.keys(), key=lambda did: rank_dict[did], reverse=True)
        ranked.append({did: idx + 1 for idx, did in enumerate(sorted_ids)})

    fused: dict[str, float] = {}
    for rank_dict, w in zip(ranked, weights):
        for doc_id, rank in rank_dict.items():
            fused[doc_id] = fused.get(doc_id, 0.0) + w / (k + rank)

    return fused


# ── search ────────────────────────────────────────────


def search(
    query: str,
    top_k: int = 10,
    fts_weight: float = 0.7,
    trgm_weight: float = 0.3,
) -> SearchResultSet:
    """
    混合检索入口（当前基于内存语料库）。

    流程：
    1. jieba 分词 → FTS 匹配（精确层，权重 0.7）
    2. pg_trgm 子串匹配（模糊层，权重 0.3）
    3. RRF 融合 → 返回 top_k

    pgvector 向量检索在 PG 环境就绪后追加为第三路（语义层）。
    """
    import time
    t0 = time.perf_counter()

    if not query.strip() or not _corpus:
        return SearchResultSet(query=query, elapsed_ms=(time.perf_counter() - t0) * 1000)

    # 1. FTS 路：jieba 分词后精确匹配
    fts_words = segment(query)
    fts_ranking: dict[str, float] = {}
    for unit in _corpus:
        content_lower = unit.content.lower()
        fts_score = 0.0
        for word in fts_words:
            word_lower = word.lower()
            count = content_lower.count(word_lower)
            if count > 0:
                # TF 加权：出现次数多 → 分数高
                fts_score += math.log1p(count)
        if fts_score > 0:
            fts_ranking[str(unit.id)] = fts_score

    # 2. Trgm 路：子串匹配（模拟 pg_trgm similarity）
    trgm_ranking: dict[str, float] = {}
    q_lower = query.lower()
    for unit in _corpus:
        content_lower = unit.content.lower()
        # 简单的词条重叠率模拟 pg_trgm
        q_chars = set(q_lower.replace(" ", ""))
        c_chars = set(content_lower.replace(" ", ""))
        if q_chars:
            overlap = len(q_chars & c_chars) / len(q_chars)
            if overlap > 0.15:  # 弱相似度阈值
                trgm_ranking[str(unit.id)] = overlap

    # 3. RRF 融合
    fused = _rrf(
        [fts_ranking, trgm_ranking],
        weights=[fts_weight, trgm_weight],
    )

    # 排序 + 取 top_k
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
