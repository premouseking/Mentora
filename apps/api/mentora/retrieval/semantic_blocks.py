"""
命中 EvidenceUnit 扩展为完整语义块。

约定：
- 细粒度 EvidenceUnit / Sentence 仅用于召回定位
- 返回给模型与前端引用的 content 必须是可独立理解的语义块
- 优先使用覆盖该 EvidenceUnit 的 ChunkProjection；缺失时按同页相邻单元扩展

约束：
- 保留 anchor evidence_id 供审计，不依赖其作为用户可见正文
- 扩展不得跨页、跨 source_version_id

@see docs/architecture/technical-solution.md §6
@module mentora/retrieval/semantic_blocks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 语义块最小字符数；短于该值时尝试向前后相邻 EvidenceUnit 扩展
MIN_SEMANTIC_CHARS = 80

# 章节边界：heading 单独成段，扩展时不跨入新的 heading 块
_BOUNDARY_TYPES = frozenset({"heading", "table", "formula"})


@dataclass
class SemanticBlock:
    """单条检索结果的语义块视图。"""

    evidence_id: str
    content: str
    matched_preview: str
    page_number: int
    block_evidence_count: int
    source_version_id: str = ""
    source_title: str = ""


def _unit_sort_key(unit: Any) -> tuple:
    indices = getattr(unit, "element_indices", None) or []
    first_idx = min(indices) if indices else 0
    return (getattr(unit, "page_number", 0), first_idx, str(getattr(unit, "id", "")))


def _is_section_boundary(current: Any, nxt: Any) -> bool:
    """判断相邻 EvidenceUnit 之间是否应停止扩展。"""
    nxt_type = getattr(nxt, "structure_type", "") or ""
    if nxt_type in _BOUNDARY_TYPES:
        return True
    cur_page = getattr(current, "page_number", None)
    nxt_page = getattr(nxt, "page_number", None)
    return cur_page is not None and nxt_page is not None and cur_page != nxt_page


def _join_contents(parts: list[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _expand_adjacent_on_page(
    unit: Any,
    page_units: list[Any],
) -> tuple[str, int]:
    """同页按 element_indices 向前后扩展，直到达到最小长度或遇到章节边界。"""
    ordered = sorted(page_units, key=_unit_sort_key)
    unit_id = str(getattr(unit, "id", ""))
    try:
        anchor_idx = next(i for i, item in enumerate(ordered) if str(item.id) == unit_id)
    except StopIteration:
        return unit.content, 1

    start = anchor_idx
    end = anchor_idx
    parts = [ordered[anchor_idx].content]

    while start > 0 and len(_join_contents(parts)) < MIN_SEMANTIC_CHARS:
        prev = ordered[start - 1]
        if _is_section_boundary(prev, ordered[start]):
            break
        start -= 1
        parts.insert(0, prev.content)

    while end < len(ordered) - 1 and len(_join_contents(parts)) < MIN_SEMANTIC_CHARS:
        nxt = ordered[end + 1]
        if _is_section_boundary(ordered[end], nxt):
            break
        end += 1
        parts.append(nxt.content)

    return _join_contents(parts), end - start + 1


def _find_chunk_content(
    evidence_id: str,
    chunks_by_evidence: dict[str, list[Any]],
) -> tuple[str, int] | None:
    """取覆盖该 EvidenceUnit 的最小 Chunk（证据数最少，语义最聚焦）。"""
    chunks = chunks_by_evidence.get(evidence_id) or []
    if not chunks:
        return None

    def _chunk_size(chunk: Any) -> int:
        ids = getattr(chunk, "evidence_ids", None) or []
        return len(ids)

    best = min(chunks, key=_chunk_size)
    ids = getattr(best, "evidence_ids", None) or []
    return best.content, len(ids)


def _build_chunks_by_evidence(chunks: list[Any]) -> dict[str, list[Any]]:
    mapping: dict[str, list[Any]] = {}
    for chunk in chunks:
        for eid in getattr(chunk, "evidence_ids", None) or []:
            mapping.setdefault(str(eid), []).append(chunk)
    return mapping


def _build_page_units_map(units: list[Any]) -> dict[tuple[str, int], list[Any]]:
    pages: dict[tuple[str, int], list[Any]] = {}
    for unit in units:
        key = (str(getattr(unit, "source_version_id", "")), int(getattr(unit, "page_number", 0)))
        pages.setdefault(key, []).append(unit)
    return pages


def expand_evidence_units_to_blocks(
    anchor_units: list[Any],
    *,
    source_titles: dict[str, str] | None = None,
) -> dict[str, SemanticBlock]:
    """
    批量将 EvidenceUnit 扩展为语义块。

    参数 anchor_units：命中的 EvidenceUnit ORM 或等价对象列表。
    返回 {evidence_id: SemanticBlock}。
    """
    if not anchor_units:
        return {}

    from mentora.retrieval.models import ChunkProjection, EvidenceUnit

    source_version_ids = {
        str(getattr(unit, "source_version_id", ""))
        for unit in anchor_units
        if getattr(unit, "source_version_id", None)
    }
    page_keys = {
        (str(getattr(unit, "source_version_id", "")), int(getattr(unit, "page_number", 0)))
        for unit in anchor_units
    }

    # 预加载同页全部 EvidenceUnit，供相邻扩展
    scope_units: list[Any] = []
    for sv_id, page_no in page_keys:
        scope_units.extend(
            EvidenceUnit.objects.filter(
                source_version_id=sv_id,
                page_number=page_no,
            )
        )

    page_units_map = _build_page_units_map(scope_units)

    chunks = list(
        ChunkProjection.objects.filter(source_version_id__in=source_version_ids)
    ) if source_version_ids else []
    chunks_by_evidence = _build_chunks_by_evidence(chunks)

    titles = source_titles or {}
    blocks: dict[str, SemanticBlock] = {}

    for unit in anchor_units:
        eid = str(unit.id)
        sv_id = str(getattr(unit, "source_version_id", ""))
        matched_preview = unit.content

        chunk_hit = _find_chunk_content(eid, chunks_by_evidence)
        if chunk_hit is not None:
            content, count = chunk_hit
        else:
            page_key = (sv_id, int(getattr(unit, "page_number", 0)))
            content, count = _expand_adjacent_on_page(
                unit,
                page_units_map.get(page_key, [unit]),
            )

        blocks[eid] = SemanticBlock(
            evidence_id=eid,
            content=content,
            matched_preview=matched_preview,
            page_number=int(getattr(unit, "page_number", 0)),
            block_evidence_count=count,
            source_version_id=sv_id,
            source_title=titles.get(sv_id, ""),
        )

    return blocks


def expand_results_to_semantic_blocks(
    results: list[Any],
    *,
    source_titles: dict[str, str] | None = None,
) -> list[Any]:
    """
    为 SearchResult 列表填充 semantic_content 等字段。

    约定：results 元素需有 .evidence.id / .content / .page_number。
    """
    if not results:
        return results

    from mentora.retrieval.models import EvidenceUnit

    evidence_ids = [str(item.evidence.id) for item in results]
    orm_units = {
        str(unit.id): unit
        for unit in EvidenceUnit.objects.filter(id__in=evidence_ids)
    }

    anchor_units = [orm_units[eid] for eid in evidence_ids if eid in orm_units]
    blocks = expand_evidence_units_to_blocks(anchor_units, source_titles=source_titles)

    for item in results:
        eid = str(item.evidence.id)
        block = blocks.get(eid)
        if block is None:
            continue
        item.semantic_content = block.content
        item.matched_preview = block.matched_preview
        item.block_evidence_count = block.block_evidence_count
        item.source_title = block.source_title

    return results


def expand_memory_results_to_semantic_blocks(results: list[Any]) -> list[Any]:
    """
    内存检索回退：corpus 已在内存，直接按同页相邻规则扩展。
    """
    if not results:
        return results

    units = [item.evidence for item in results]
    page_units_map = _build_page_units_map(units)

    for item in results:
        unit = item.evidence
        page_key = (
            str(getattr(unit, "source_version_id", "")),
            int(getattr(unit, "page_number", 0)),
        )
        content, count = _expand_adjacent_on_page(
            unit,
            page_units_map.get(page_key, [unit]),
        )
        item.semantic_content = content
        item.matched_preview = unit.content
        item.block_evidence_count = count
        item.source_title = ""

    return results
