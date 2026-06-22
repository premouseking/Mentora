"""Database-backed retrieval benchmark helpers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from mentora.retrieval.search import SearchResultSet, async_search


@dataclass
class QueryBenchmark:
    query: str
    query_type: str
    expected_ids: list[str]
    result_set: SearchResultSet | None = None
    p_at_5: float = 0.0
    p_at_10: float = 0.0
    recall: float = 0.0
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "expected_count": len(self.expected_ids),
            "returned_count": len(self.result_set.results) if self.result_set else 0,
            "p_at_5": round(self.p_at_5, 3),
            "p_at_10": round(self.p_at_10, 3),
            "recall": round(self.recall, 3),
            "elapsed_ms": round(self.elapsed_ms, 1),
            "hits": [
                r.to_dict() for r in (self.result_set.results if self.result_set else [])
            ],
        }


@dataclass
class RetrievalBenchmarkReport:
    queries: list[QueryBenchmark]
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "queries": [q.to_dict() for q in self.queries],
            "summary": {
                "total_queries": len(self.queries),
                "avg_p_at_5": round(
                    sum(q.p_at_5 for q in self.queries) / max(len(self.queries), 1), 3
                ),
                "avg_p_at_10": round(
                    sum(q.p_at_10 for q in self.queries) / max(len(self.queries), 1), 3
                ),
                "avg_recall": round(
                    sum(q.recall for q in self.queries) / max(len(self.queries), 1), 3
                ),
            },
            "generated_at": self.generated_at,
        }


def _precision_at_k(result_ids: list[str], expected: set[str], k: int) -> float:
    if not result_ids or not expected:
        return 0.0
    return len(set(result_ids[:k]) & expected) / k


def _recall_at_k(result_ids: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    return len(set(result_ids[:k]) & expected) / len(expected)


async def run_retrieval_benchmark(
    benchmarks: list[dict],
    *,
    source_version_ids: list[str] | None = None,
) -> RetrievalBenchmarkReport:
    """Run benchmark queries against persisted retrieval tables."""
    results: list[QueryBenchmark] = []
    for bm in benchmarks:
        expected = set(bm["expected_ids"])
        started_at = time.perf_counter()
        rs = await async_search(
            bm["query"],
            top_k=10,
            source_version_ids=source_version_ids,
        )
        elapsed = (time.perf_counter() - started_at) * 1000
        result_ids = [str(r.evidence.id) for r in rs.results]

        results.append(
            QueryBenchmark(
                query=bm["query"],
                query_type=bm.get("query_type", "exact"),
                expected_ids=list(expected),
                result_set=rs,
                p_at_5=_precision_at_k(result_ids, expected, 5),
                p_at_10=_precision_at_k(result_ids, expected, 10),
                recall=_recall_at_k(result_ids, expected, 10),
                elapsed_ms=elapsed,
            )
        )

    return RetrievalBenchmarkReport(
        queries=results,
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def _make_gold_benchmarks() -> list[dict]:
    return [
        {
            "query": "直接映射",
            "query_type": "exact",
            "expected_ids": ["e8d1a2b3-0001-4000-8000-000000000001"],
        },
        {
            "query": "Cache 映射方式",
            "query_type": "exact",
            "expected_ids": [
                "e8d1a2b3-0001-4000-8000-000000000001",
                "e8d1a2b3-0001-4000-8000-000000000002",
            ],
        },
        {
            "query": "LRU",
            "query_type": "abbreviation",
            "expected_ids": ["e8d1a2b3-0001-4000-8000-000000000003"],
        },
        {
            "query": "cache的对应方式",
            "query_type": "fuzzy",
            "expected_ids": [
                "e8d1a2b3-0001-4000-8000-000000000001",
                "e8d1a2b3-0001-4000-8000-000000000002",
            ],
        },
        {
            "query": "梯度下降优化",
            "query_type": "exact",
            "expected_ids": ["e8d1a2b3-0001-4000-8000-000000000007"],
        },
    ]


def run() -> RetrievalBenchmarkReport:
    """Run the built-in benchmark against the current database."""
    return asyncio.run(run_retrieval_benchmark(_make_gold_benchmarks()))
