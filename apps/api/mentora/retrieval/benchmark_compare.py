"""
检索粒度对比基准：EvidenceUnit vs ChunkProjection vs SentenceProjection。

约定：
- 使用同一套金标查询，同一套 PDF Fixture 解析产物
- 每种粒度独立建表、独立检索、独立评估
- 对比 P@5/P@10/Recall 三项指标

@module mentora.retrieval.benchmark_compare
"""

import os
import time
from dataclasses import dataclass, field

from django.db import connection

from mentora.parsing.adapters import parse
from mentora.parsing.evidence import split_evidence
from mentora.retrieval.chunk_builder import build_chunks
from mentora.retrieval.sentence_splitter import generate_sentence_projections


def _search_table(table: str, query: str, top_k: int = 10) -> list[str]:
    """
    对指定表执行 jieba ILIKE 检索，返回匹配的 ID 列表。
    """
    from mentora.retrieval.tokenizer import segment

    words = segment(query)
    if not words:
        return []

    clauses = " AND ".join([f"{table}.content ILIKE %s"] * len(words))
    params = [f"%{w}%" for w in words]

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id::text FROM {table} WHERE {clauses} LIMIT %s",
            [*params, top_k],
        )
        return [row[0] for row in cursor.fetchall()]


def _precision_at_k(returned: list[str], expected: set[str], k: int) -> float:
    if not returned or not expected:
        return 0.0
    return len(set(returned[:k]) & expected) / k


def _recall_at_k(returned: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    return len(set(returned[:k]) & expected) / len(expected)


def run() -> dict:
    """
    执行三粒度对比基准，返回汇总字典。
    """
    # __file__: .../apps/api/mentora/retrieval/benchmark_compare.py
    # ../.. → .../apps/api/  →  tests/fixtures → .../apps/api/tests/fixtures
    base = os.path.dirname(os.path.abspath(__file__))
    fixtures_dir = os.path.join(base, "..", "..", "tests", "fixtures")
    fixtures_dir = os.path.abspath(fixtures_dir)

    # ── 1. 清空并重建数据 ──────────────────────
    from mentora.retrieval.models import (
        ChunkProjection,
        EvidenceUnit,
        SentenceProjection,
    )

    EvidenceUnit.objects.all().delete()
    ChunkProjection.objects.all().delete()
    SentenceProjection.objects.all().delete()

    import jieba
    from django.contrib.postgres.search import SearchVector

    all_evidence: list = []
    ev_id_to_content: dict[str, str] = {}

    for filename in sorted(os.listdir(fixtures_dir)):
        if not filename.endswith(".pdf"):
            continue
        filepath = os.path.join(fixtures_dir, filename)
        try:
            bundle = parse(filepath, "1.0.0")
        except Exception:
            continue

        for eu in split_evidence(bundle):
            segmented = " ".join(jieba.cut(eu.content))
            unit = EvidenceUnit.objects.create(
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
            unit.search_vector = SearchVector("segmented_content", config="simple")
            unit.save(update_fields=["search_vector"])
            all_evidence.append(unit)
            ev_id_to_content[str(unit.id)] = unit.content

            # 句子拆分
            for proj in generate_sentence_projections(unit.id, unit.content):
                proj.save()

    # Chunk: 按 source_version_id 分组后聚合
    sv_ids = set(u.source_version_id for u in all_evidence)
    for sv_id in sv_ids:
        sv_units = [u for u in all_evidence if u.source_version_id == sv_id]
        for chunk in build_chunks(sv_units):
            chunk.save()

    # ── 2. 获取 ID→content 映射 ────────────────
    with connection.cursor() as c:
        c.execute("SELECT id, content FROM retrieval_evidence_unit")
        ev_map = {str(r[0]): r[1] for r in c.fetchall()}
        c.execute("SELECT id, content FROM retrieval_chunk_projection")
        ch_map = {str(r[0]): r[1] for r in c.fetchall()}
        c.execute("SELECT id, content FROM retrieval_sentence_projection")
        se_map = {str(r[0]): r[1] for r in c.fetchall()}

    # ── 3. 金标查询 ─────────────────────────────
    gold_queries = [
        {"query": "计算机系统概述", "keywords": ["计算机系统概述"]},
        {"query": "Cache 存储原理", "keywords": ["Cache"]},
        {"query": "计算机组成原理", "keywords": ["计算机组成原理"]},
        {"query": "Cache", "keywords": ["Cache"]},
        {"query": "存储", "keywords": ["存储"]},
        {"query": "考研", "keywords": ["考研"]},
    ]

    # ── 4. 评估 ─────────────────────────────────
    tables = {
        "EvidenceUnit": ("retrieval_evidence_unit", ev_map),
        "ChunkProjection": ("retrieval_chunk_projection", ch_map),
        "SentenceProjection": ("retrieval_sentence_projection", se_map),
    }

    results: list[dict] = []
    for gq in gold_queries:
        row = {"query": gq["query"]}
        for label, (tbl, id_map) in tables.items():
            t0 = time.perf_counter()
            returned = _search_table(tbl, gq["query"])
            elapsed = (time.perf_counter() - t0) * 1000

            expected = {
                eid for eid, content in id_map.items()
                if all(kw in content for kw in gq["keywords"])
            }

            row[f"{label}_expected"] = len(expected)
            row[f"{label}_returned"] = len(returned)
            row[f"{label}_P@5"] = round(_precision_at_k(returned, expected, 5), 3)
            row[f"{label}_P@10"] = round(_precision_at_k(returned, expected, 10), 3)
            row[f"{label}_Recall"] = round(_recall_at_k(returned, expected, 10), 3)
            row[f"{label}_ms"] = round(elapsed, 1)
        results.append(row)

    # ── 5. 汇总 ─────────────────────────────────
    summary = {}
    for label in tables:
        summary[f"{label}_avg_P@5"] = round(
            sum(r[f"{label}_P@5"] for r in results) / max(len(results), 1), 3
        )
        summary[f"{label}_avg_P@10"] = round(
            sum(r[f"{label}_P@10"] for r in results) / max(len(results), 1), 3
        )
        summary[f"{label}_avg_Recall"] = round(
            sum(r[f"{label}_Recall"] for r in results) / max(len(results), 1), 3
        )
        summary[f"{label}_avg_ms"] = round(
            sum(r[f"{label}_ms"] for r in results) / max(len(results), 1), 1
        )

    counts = {
        "evidence_count": len(ev_map),
        "chunk_count": len(ch_map),
        "sentence_count": len(se_map),
    }

    return {"queries": results, "summary": summary, "counts": counts}
