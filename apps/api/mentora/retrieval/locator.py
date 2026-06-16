"""
引用定位服务：从 EvidenceUnit ID 返回精确定位信息，供前端跳转原文。

约定：
- 定位结果包含页码、坐标 BoundingBox、正文内容和上下文窗口
- 上下文窗口限制在同一页内（不跨页取相邻证据）
- 句级定位通过 SentenceProjection 实现（按需生成）
- 无效 ID 返回 None，不抛异常（调用方自行处理空结果）

输出结构：
{
  evidence_id, page_number, bbox, content,
  context_before (同页前一个 EvidenceUnit 的 content),
  context_after (同页后一个 EvidenceUnit 的 content),
  sentences: [{position_index, content}, ...]
}

@module mentora/retrieval/locator
"""

from dataclasses import dataclass, field


@dataclass
class SentenceLocation:
    position_index: int
    content: str


@dataclass
class CitationLocation:
    evidence_id: str
    page_number: int
    bbox: dict | None = None
    content: str = ""
    context_before: str | None = None
    context_after: str | None = None
    sentences: list[SentenceLocation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "content": self.content,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "sentences": [
                {"position_index": s.position_index, "content": s.content}
                for s in self.sentences
            ],
        }


# ── in-memory corpus (for API when DB is unavailable) ───

_corpus: dict[str, "EvidenceUnit"] = {}
_corpus_ordered: list["EvidenceUnit"] = []


def load_corpus(units: list) -> None:
    """加载 EvidenceUnit 列表作为内存语料库。"""
    global _corpus, _corpus_ordered
    _corpus = {str(u.id): u for u in units}
    _corpus_ordered = list(units)


# ── public API ─────────────────────────────────────────


def locate_evidence(evidence_id: str) -> CitationLocation | None:
    """
    查询引用定位。优先使用内存语料库，ORM 不可用时回退。

    输入：EvidenceUnit.id 的字符串形式
    返回：CitationLocation 或 None（ID 不存在时）
    """
    if _corpus:
        return _locate_from_corpus(evidence_id)

    try:
        return _locate_from_orm(evidence_id)
    except Exception:
        return None


def locate_evidence_batch(evidence_ids: list[str]) -> dict[str, CitationLocation | None]:
    """批量定位。"""
    if _corpus:
        return {
            eid: _locate_from_corpus(eid) for eid in evidence_ids
        }

    try:
        from mentora.retrieval.repository import get_evidence_by_ids_ordered
        units = get_evidence_by_ids_ordered(evidence_ids)
        result: dict[str, CitationLocation | None] = {eid: None for eid in evidence_ids}
        for unit in units:
            eid = str(unit.id)
            ctx_before, ctx_after = _get_adjacent_context(unit)
            sentences = _get_sentence_locations(eid)
            result[eid] = CitationLocation(
                evidence_id=eid,
                page_number=unit.page_number,
                bbox=unit.bbox_json,
                content=unit.content,
                context_before=ctx_before,
                context_after=ctx_after,
                sentences=sentences,
            )
        return result
    except Exception:
        return {eid: None for eid in evidence_ids}


# ── in-memory implementation ───────────────────────────


def _locate_from_corpus(evidence_id: str) -> CitationLocation | None:
    """从内存语料库查询引用定位。"""
    unit = _corpus.get(evidence_id)
    if unit is None:
        return None

    # 上下文：同页相邻
    ctx_before = None
    ctx_after = None
    for i, u in enumerate(_corpus_ordered):
        if str(u.id) == evidence_id:
            if i > 0 and _corpus_ordered[i - 1].page_number == unit.page_number:
                ctx_before = _corpus_ordered[i - 1].content[-300:]
            if i + 1 < len(_corpus_ordered) and _corpus_ordered[i + 1].page_number == unit.page_number:
                ctx_after = _corpus_ordered[i + 1].content[:300]
            break

    return CitationLocation(
        evidence_id=evidence_id,
        page_number=unit.page_number,
        bbox=unit.bbox.model_dump() if hasattr(unit.bbox, "model_dump") else unit.bbox,
        content=unit.content,
        context_before=ctx_before,
        context_after=ctx_after,
    )


# ── ORM implementation ────────────────────────────────


def _locate_from_orm(evidence_id: str) -> CitationLocation | None:
    """通过 Django ORM 查询引用定位。"""
    from mentora.retrieval.repository import (
        get_evidence_by_ids,
        get_sentences_by_evidence,
    )

    units = list(get_evidence_by_ids([evidence_id]))
    if not units:
        return None

    unit = units[0]
    ctx_before, ctx_after = _get_adjacent_context(unit)
    sentences = _get_sentence_locations(evidence_id)

    return CitationLocation(
        evidence_id=str(unit.id),
        page_number=unit.page_number,
        bbox=unit.bbox_json,
        content=unit.content,
        context_before=ctx_before,
        context_after=ctx_after,
        sentences=sentences,
    )


# ── helpers ────────────────────────────────────────────


def _get_adjacent_context(unit) -> tuple[str | None, str | None]:
    """
    获取同页内前后相邻 EvidenceUnit 的内容。

    约束：不跨页取上下文。如果前后没有同页证据，对应位置为 None。
    """
    from mentora.retrieval.models import EvidenceUnit
    from django.db.models import Q

    # 前一个同页证据（按 id 排序取最近一个）
    prev_unit = (
        EvidenceUnit.objects.filter(
            source_version_id=unit.source_version_id,
            page_number=unit.page_number,
            id__lt=unit.id,
        )
        .order_by("-id")
        .first()
    )

    # 后一个同页证据
    next_unit = (
        EvidenceUnit.objects.filter(
            source_version_id=unit.source_version_id,
            page_number=unit.page_number,
            id__gt=unit.id,
        )
        .order_by("id")
        .first()
    )

    return (
        prev_unit.content[-300:] if prev_unit else None,
        next_unit.content[:300] if next_unit else None,
    )


def _get_sentence_locations(evidence_id: str) -> list[SentenceLocation]:
    """
    获取指定 EvidenceUnit 的句级定位。

    如果 SentenceProjection 表中不存在记录（未按需生成），返回空列表。
    """
    from mentora.retrieval.repository import get_sentences_by_evidence

    sentences = list(get_sentences_by_evidence(evidence_id))
    return [
        SentenceLocation(position_index=s.position_index, content=s.content)
        for s in sentences
    ]
