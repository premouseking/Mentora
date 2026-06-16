"""
端到端检索基准：解析 PDF → EvidenceUnit 入库 → 检索评估。

约定：
- 使用 tests/fixtures/ 下的 PDF 文件作为语料来源
- 金标查询针对解析后生成的 EvidenceUnit 标注预期命中 ID
- 评估 P@5、P@10、Recall@10 三项指标

约束：
- 重复运行前清空 EvidenceUnit 表，避免重复数据
- 每个查询类型覆盖精确/模糊/缩写三种场景

@module mentora.retrieval.benchmark_runner
"""

import os
import time
from dataclasses import dataclass, field

from django.db import connection

from mentora.parsing.adapters import parse
from mentora.parsing.evidence import split_evidence
from mentora.retrieval.search import _search_pg, load_corpus


@dataclass
class QueryResult:
    query: str
    query_type: str  # "exact" | "fuzzy" | "abbreviation"
    expected_ids: list[str]
    returned_ids: list[str]
    p_at_5: float = 0.0
    p_at_10: float = 0.0
    recall: float = 0.0
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "expected_count": len(self.expected_ids),
            "returned_count": len(self.returned_ids),
            "p_at_5": round(self.p_at_5, 3),
            "p_at_10": round(self.p_at_10, 3),
            "recall": round(self.recall, 3),
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


@dataclass
class BenchmarkReport:
    queries: list[QueryResult] = field(default_factory=list)
    corpus_size: int = 0
    parser_name: str = ""
    parser_version: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        qs = [q.to_dict() for q in self.queries]
        n = max(len(qs), 1)
        return {
            "corpus_size": self.corpus_size,
            "parser": f"{self.parser_name} v{self.parser_version}",
            "queries": qs,
            "summary": {
                "total_queries": len(qs),
                "avg_p_at_5": round(sum(q.p_at_5 for q in self.queries) / n, 3),
                "avg_p_at_10": round(sum(q.p_at_10 for q in self.queries) / n, 3),
                "avg_recall": round(sum(q.recall for q in self.queries) / n, 3),
            },
            "generated_at": self.generated_at,
        }


# ── helpers ────────────────────────────────────────────


def _precision_at_k(returned: list[str], expected: set[str], k: int) -> float:
    if not returned or not expected:
        return 0.0
    return len(set(returned[:k]) & expected) / k


def _recall_at_k(returned: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    return len(set(returned[:k]) & expected) / len(expected)


# ── persist ────────────────────────────────────────────


def _load_evidence_into_db(fixtures_dir: str) -> int:
    """
    遍历 fixtures_dir 下所有 PDF，解析后写入 retrieval_evidence_unit 表。
    写入时自动生成 jieba 分词后的 segmented_content 和 PG search_vector。
    返回入库总数。
    """
    import jieba
    from django.contrib.postgres.search import SearchVector
    from mentora.retrieval.models import EvidenceUnit as ORMEvidenceUnit

    # 清空已有数据
    ORMEvidenceUnit.objects.all().delete()

    total = 0
    for filename in sorted(os.listdir(fixtures_dir)):
        if not filename.endswith(".pdf"):
            continue

        filepath = os.path.join(fixtures_dir, filename)
        try:
            bundle = parse(filepath, parser_version="1.0.0")
        except Exception:
            continue

        evidence_units = split_evidence(bundle)

        for eu in evidence_units:
            # jieba 分词 → 空格分隔
            segmented = " ".join(jieba.cut(eu.content))

            unit = ORMEvidenceUnit.objects.create(
                id=eu.id,
                source_version_id=f"fixture-{filename}",
                bundle_id=eu.bundle_id,
                content=eu.content,
                segmented_content=segmented,
                page_number=eu.page_number,
                bbox_json=eu.bbox.model_dump() if eu.bbox else None,
                element_indices=eu.element_indices,
                structure_type="paragraph",
            )
            # 填充 search_vector（PG tsvector）
            unit.search_vector = SearchVector("segmented_content", config="simple")
            unit.save(update_fields=["search_vector"])
            total += 1

    return total


# ── gold queries ────────────────────────────────────────


def _build_gold_queries() -> list[dict]:
    """
    金标查询定义。

    查询语义基于已知 Fixture 内容：
    - normal.pdf: 包含"计算机系统概述"、"硬件"、"软件"等
    - headings.pdf: 包含"计算机组成原理"、"存储系统"、"Cache"等
    - multi_column.pdf: 包含"组成原理"、"考研"、"唐朔飞"等
    """
    return [
        # ── 精确匹配 ──
        {
            "query": "计算机系统概述",
            "query_type": "exact",
            "match_content_contains": ["计算机系统概述"],
        },
        {
            "query": "Cache 存储原理",
            "query_type": "exact",
            "match_content_contains": ["Cache"],
        },
        {
            "query": "计算机组成原理",
            "query_type": "exact",
            "match_content_contains": ["计算机组成原理"],
        },

        # ── 缩写/英文 ──
        {
            "query": "Cache",
            "query_type": "abbreviation",
            "match_content_contains": ["Cache"],
        },

        # ── 模糊输入 ──
        {
            "query": "存储",
            "query_type": "fuzzy",
            "match_content_contains": ["存储"],
        },
        {
            "query": "考研",
            "query_type": "fuzzy",
            "match_content_contains": ["考研"],
        },
    ]


# ── main ────────────────────────────────────────────────


def run() -> BenchmarkReport:
    """
    端到端检索基准主入口。

    1. 解析 PDF → EvidenceUnit 入库
    2. 对每个金标查询执行 PG 检索
    3. 用内容关键词（match_content_contains）匹配预期 ID
    4. 计算 P@5/P@10/Recall
    """
    fixtures_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "fixtures"
    )
    fixtures_dir = os.path.abspath(fixtures_dir)

    # 1. 入库
    corpus_size = _load_evidence_into_db(fixtures_dir)

    # 2. 获取入库后的 ID→content 映射
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, content FROM retrieval_evidence_unit")
        id_to_content: dict[str, str] = {}
        for row in cursor.fetchall():
            id_to_content[str(row[0])] = row[1]

    # 3. 执行金标查询
    gold_queries = _build_gold_queries()
    query_results: list[QueryResult] = []

    for gq in gold_queries:
        keywords = gq["match_content_contains"]

        # 找出预期命中的 ID（内容包含所有关键词）
        expected_ids = [
            eid for eid, content in id_to_content.items()
            if all(kw.lower() in content.lower() for kw in keywords)
        ]

        # 执行检索
        t0 = time.perf_counter()
        rs = _search_pg(gq["query"], top_k=10, fts_weight=0.7, trgm_weight=0.3)
        elapsed = (time.perf_counter() - t0) * 1000

        returned_ids = [str(r.evidence.id) for r in rs.results]
        expected_set = set(expected_ids)

        query_results.append(QueryResult(
            query=gq["query"],
            query_type=gq["query_type"],
            expected_ids=expected_ids,
            returned_ids=returned_ids,
            p_at_5=_precision_at_k(returned_ids, expected_set, 5),
            p_at_10=_precision_at_k(returned_ids, expected_set, 10),
            recall=_recall_at_k(returned_ids, expected_set, 10),
            elapsed_ms=elapsed,
        ))

    return BenchmarkReport(
        queries=query_results,
        corpus_size=corpus_size,
        parser_name="pymupdf",
        parser_version="1.0.0",
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
