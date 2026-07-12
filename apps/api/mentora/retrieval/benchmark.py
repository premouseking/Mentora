"""
检索基准测试。

约定：
- 使用已知的 EvidenceUnit 集合和预期命中作为金标集
- 每次运行输出每个查询的 P@5、P@10、Recall@10
- 评估区分「分词精度」与「排序质量」

约束：
- 不依赖外部服务或数据库
- 基准查询覆盖精确术语、模糊输入和简写三种场景

@module mentora/retrieval/benchmark
"""

import time
from dataclasses import dataclass, field

from mentora.parsing.schemas import EvidenceUnit
from mentora.retrieval.search import SearchResultSet, load_corpus, search


@dataclass
class QueryBenchmark:
    """单个查询的基准结果。"""
    query: str
    query_type: str  # "exact" | "fuzzy" | "abbreviation"
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
    """检索基准完整报告。"""
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
    top_k = set(result_ids[:k])
    return len(top_k & expected) / k


def _recall_at_k(result_ids: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    top_k = set(result_ids[:k])
    return len(top_k & expected) / len(expected)


def run_retrieval_benchmark(
    corpus: list[EvidenceUnit],
    benchmarks: list[dict],
) -> RetrievalBenchmarkReport:
    """
    运行检索基准测试。

    benchmarks: [{"query": str, "query_type": str, "expected_ids": [str]}, ...]
    """
    load_corpus(corpus)

    results: list[QueryBenchmark] = []
    for bm in benchmarks:
        expected = set(bm["expected_ids"])

        t0 = time.perf_counter()
        rs = search(bm["query"], top_k=10)
        elapsed = (time.perf_counter() - t0) * 1000

        result_ids = [str(r.evidence.id) for r in rs.results]

        qb = QueryBenchmark(
            query=bm["query"],
            query_type=bm.get("query_type", "exact"),
            expected_ids=list(expected),
            result_set=rs,
            p_at_5=_precision_at_k(result_ids, expected, 5),
            p_at_10=_precision_at_k(result_ids, expected, 10),
            recall=_recall_at_k(result_ids, expected, 10),
            elapsed_ms=elapsed,
        )
        results.append(qb)

    return RetrievalBenchmarkReport(
        queries=results,
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


# ── 金标集 ────────────────────────────────────────────

def _make_gold_corpus() -> tuple[list[EvidenceUnit], list[dict]]:
    """
    构造测试用的检索语料库和基准查询。

    金标查询：
    - Q1 精确术语：搜「直接映射」应命中包含该术语的段落
    - Q2 模糊输入：搜「cache 映射」应同时命中「Cache」和「映射」
    - Q3 缩写：搜「LRU」应命中包含该缩写的段落
    """
    units = [
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000001",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="直接映射是三种 Cache 映射方式中最简单的一种。每个主存块只能放入一个固定的 Cache 行。",
            page_number=3,
            element_indices=[0],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000002",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="组相联映射折中了直接映射和全相联映射的特点，将 Cache 分成多个组。",
            page_number=3,
            element_indices=[1],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000003",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="LRU 替换策略记录每个 Cache 行的最近访问时间，淘汰最久未使用的块。",
            page_number=4,
            element_indices=[0],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000004",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="Cache 的命中率受映射方式、替换策略和 Cache 容量共同影响。",
            page_number=5,
            element_indices=[0],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000005",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="TLB 是页表的快速缓存，利用局部性原理加速地址转换。",
            page_number=6,
            element_indices=[0],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000006",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="指令流水线将指令执行过程分解为多个阶段，实现指令级并行。",
            page_number=7,
            element_indices=[0],
        ),
        EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000007",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="梯度下降通过计算损失函数的梯度来更新模型参数。",
            page_number=8,
            element_indices=[0],
        ),
    ]

    benchmarks = [
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
            "query": "cache的对应方式",  # 模拟用户输入错误
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

    return units, benchmarks


def run() -> RetrievalBenchmarkReport:
    """运行检索基准并返回报告。"""
    corpus, benchmarks = _make_gold_corpus()
    return run_retrieval_benchmark(corpus, benchmarks)
