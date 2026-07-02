"""
ParsedBundle / EvidenceUnit → LightRead-like PdfBlock 转换。

@module mentora/knowledge/layout_converter
"""

from __future__ import annotations

from mentora.knowledge.reader_contract import PdfBlock, PdfPageInfo, ReaderOutlineItem
from mentora.parsing.schemas import ParsedBundle


def bundle_to_page_infos(bundle: ParsedBundle) -> list[PdfPageInfo]:
    pages: list[PdfPageInfo] = []
    for page in bundle.pages:
        width = height = None
        page_size = getattr(page, "page_size", None)
        if page_size and len(page_size) >= 2:
            width, height = page_size[0], page_size[1]
        pages.append(PdfPageInfo(page=page.page_number, width=width, height=height))
    return pages


def bundle_to_blocks(
    bundle: ParsedBundle,
    evidence_by_element: dict[int, str] | None = None,
) -> list[PdfBlock]:
    """将 ParsedBundle 元素拍平为 PdfBlock 列表。"""
    evidence_by_element = evidence_by_element or {}
    blocks: list[PdfBlock] = []
    flat_index = 0

    for page in bundle.pages:
        for element in page.elements:
            bbox = None
            if element.bbox is not None:
                bbox = [
                    element.bbox.x0,
                    element.bbox.y0,
                    element.bbox.x1,
                    element.bbox.y1,
                ]
            blocks.append(
                PdfBlock(
                    idx=f"block-{flat_index}",
                    type=element.type.value if hasattr(element.type, "value") else str(element.type),
                    page=page.page_number,
                    bbox=bbox,
                    text=element.text or "",
                    level=element.heading_level,
                    evidence_unit_id=evidence_by_element.get(flat_index),
                )
            )
            flat_index += 1

    return blocks


def blocks_to_outline(blocks: list[PdfBlock]) -> list[ReaderOutlineItem]:
    """用 heading 块生成 fallback 目录。"""
    items: list[ReaderOutlineItem] = []
    for block in blocks:
        if block.type != "heading" or not block.text.strip():
            continue
        items.append(
            ReaderOutlineItem(
                id=f"outline-{block.idx}",
                title=block.text.strip(),
                page=block.page,
                level=block.level or 1,
                block_idx=block.idx,
            )
        )
    return items


def build_evidence_element_map(
    evidence_rows: list,
) -> dict[int, str]:
    """EvidenceUnit.element_indices → evidence_unit_id。"""
    mapping: dict[int, str] = {}
    for row in evidence_rows:
        eid = str(row.id)
        for idx in row.element_indices or []:
            if isinstance(idx, int):
                mapping[idx] = eid
    return mapping
