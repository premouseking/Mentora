"""
向量搜索基准对比：两路（FTS+Trgm） vs 三路（FTS+Trgm+Vector）。

约定：
- 使用同一套 fixture PDF 和金标查询
- 先入库 Evidence → 建 Chunk → 尝试生成 embedding
- 对比 vector_weight=0（仅两路）vs vector_weight=0.3（三路）的检索质量

@module mentora.retrieval.benchmark_vector
"""

import os
import time
from dataclasses import dataclass, field

from asgiref.sync import async_to_sync
from django.db import connection

from mentora.retrieval.benchmark_runner import (
    _load_evidence_into_db,
    _build_gold_queries,
    _precision_at_k,
    _recall_at_k,
)
from mentora.retrieval.chunk_builder import build_chunks
from mentora.retrieval.models import ChunkProjection, EvidenceUnit
from mentora.retrieval.search import async_search


@dataclass
class VectorBenchmarkRow:
    """单查询 × 单模式的基准结果。"""

    query: str
    mode: str  # "fts_trgm" | "fts_trgm_vector"
    p_at_5: float = 0.0
    p_at_10: float = 0.0
    recall: float = 0.0
    elapsed_ms: float = 0.0


@dataclass
class VectorBenchmarkReport:
    rows: list[VectorBenchmarkRow] = field(default_factory=list)
    corpus_size: int = 0
    chunk_count: int = 0
    chunk_embedded: int = 0

    def to_dict(self) -> dict:
        return {
            "corpus_size": self.corpus_size,
            "chunk_count": self.chunk_count,
            "chunk_embedded": self.chunk_embedded,
            "rows": [
                {
                    "query": r.query,
                    "mode": r.mode,
                    "p_at_5": round(r.p_at_5, 3),
                    "p_at_10": round(r.p_at_10, 3),
                    "recall": round(r.recall, 3),
                    "elapsed_ms": round(r.elapsed_ms, 1),
                }
                for r in self.rows
            ],
            "summary": self._summary(),
        }

    def _summary(self) -> dict:
        modes = {}
        for r in self.rows:
            if r.mode not in modes:
                modes[r.mode] = []
            modes[r.mode].append(r)

        result = {}
        for mode, rs in modes.items():
            n = max(len(rs), 1)
            result[mode] = {
                "avg_p_at_5": round(sum(r.p_at_5 for r in rs) / n, 3),
                "avg_p_at_10": round(sum(r.p_at_10 for r in rs) / n, 3),
                "avg_recall": round(sum(r.recall for r in rs) / n, 3),
                "avg_ms": round(sum(r.elapsed_ms for r in rs) / n, 1),
            }
        return result


def _build_chunks() -> int:
    """将 EvidenceUnit 按 source_version_id 分组聚合为 ChunkProjection。"""
    ChunkProjection.objects.all().delete()

    sv_ids = EvidenceUnit.objects.values_list(
        "source_version_id", flat=True
    ).distinct()

    total = 0
    for sv_id in sv_ids:
        units = list(
            EvidenceUnit.objects.filter(source_version_id=sv_id).order_by(
                "page_number"
            )
        )
        if not units:
            continue
        for chunk in build_chunks(units):
            chunk.save()
            total += 1
    return total


def _embed_chunks() -> int:
    """尝试为 Chunk 生成 embedding，返回成功数。无 API key 时返回 0。"""
    try:
        from mentora.retrieval.tasks import generate_chunk_embeddings

        result = generate_chunk_embeddings()
        return result.get("processed", 0)
    except Exception:
        return 0


def run() -> VectorBenchmarkReport:
    """
    向量基准对比主入口。

    1. 解析 PDF → EvidenceUnit 入库
    2. 聚合为 ChunkProjection
    3. 尝试生成 embedding（无 API key 则跳过）
    4. vector_weight=0 检索 → 评估
    5. vector_weight=0.3 检索 → 评估
    6. 生成对比报告
    """
    fixtures_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "fixtures"
    )
    fixtures_dir = os.path.abspath(fixtures_dir)

    # 1-3. 入库
    corpus_size = _load_evidence_into_db(fixtures_dir)
    chunk_count = _build_chunks()
    chunk_embedded = _embed_chunks()

    # 4. 获取 ID→content 映射
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, content FROM retrieval_evidence_unit")
        id_to_content: dict[str, str] = {}
        for row in cursor.fetchall():
            id_to_content[str(row[0])] = row[1]

    # 5. 执行对比
    gold_queries = _build_gold_queries()
    rows: list[VectorBenchmarkRow] = []

    for gq in gold_queries:
        keywords = gq["match_content_contains"]
        expected_ids = [
            eid for eid, content in id_to_content.items()
            if all(kw.lower() in content.lower() for kw in keywords)
        ]
        expected_set = set(expected_ids)

        # ── 两路 ──
        t0 = time.perf_counter()
        rs_two = async_to_sync(async_search)(
            gq["query"],
            top_k=10,
            fts_weight=0.7,
            trgm_weight=0.3,
            vector_weight=0,
        )
        elapsed_two = (time.perf_counter() - t0) * 1000
        returned_two = [str(r.evidence.id) for r in rs_two.results]

        rows.append(VectorBenchmarkRow(
            query=gq["query"],
            mode="fts_trgm",
            p_at_5=_precision_at_k(returned_two, expected_set, 5),
            p_at_10=_precision_at_k(returned_two, expected_set, 10),
            recall=_recall_at_k(returned_two, expected_set, 10),
            elapsed_ms=elapsed_two,
        ))

        # ── 三路 ──
        t0 = time.perf_counter()
        rs_three = async_to_sync(async_search)(
            gq["query"],
            top_k=10,
            fts_weight=0.5,
            trgm_weight=0.2,
            vector_weight=0.3,
        )
        elapsed_three = (time.perf_counter() - t0) * 1000
        returned_three = [str(r.evidence.id) for r in rs_three.results]

        rows.append(VectorBenchmarkRow(
            query=gq["query"],
            mode="fts_trgm_vector",
            p_at_5=_precision_at_k(returned_three, expected_set, 5),
            p_at_10=_precision_at_k(returned_three, expected_set, 10),
            recall=_recall_at_k(returned_three, expected_set, 10),
            elapsed_ms=elapsed_three,
        ))

    return VectorBenchmarkReport(
        rows=rows,
        corpus_size=corpus_size,
        chunk_count=chunk_count,
        chunk_embedded=chunk_embedded,
    )
