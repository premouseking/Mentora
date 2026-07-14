"""
从 ParsedBundle 拆分 EvidenceUnit。

约定：
- 同页连续 paragraph / list_item 聚合为一个块级 EvidenceUnit
- heading 与其后第一个 paragraph 合并为一个证据单元（保留上下文）
- EvidenceUnit 通过 element_indices 引用 ParsedElement（0-based，拍平后索引）

约束：
- EvidenceUnit 不复制坐标数据
- 空白元素（text 为空）不生成 EvidenceUnit
- 每个 EvidenceUnit 必须有 page_number

@module mentora/parsing/evidence
"""

from mentora.parsing.schemas import BoundingBox, ElementType, EvidenceUnit, ParsedBundle, ParsedElement

# 同页连续文本流元素可聚合为一块
_TEXT_FLOW_TYPES = frozenset({ElementType.PARAGRAPH, ElementType.LIST_ITEM})


def _merge_bboxes(boxes: list[BoundingBox | None]) -> BoundingBox | None:
    valid = [box for box in boxes if box is not None]
    if not valid:
        return None
    return BoundingBox(
        x0=min(box.x0 for box in valid),
        y0=min(box.y0 for box in valid),
        x1=max(box.x1 for box in valid),
        y1=max(box.y1 for box in valid),
    )


def _structure_type_for_elements(elements: list[ParsedElement]) -> str:
    if not elements:
        return "paragraph"
    if len(elements) == 1:
        return elements[0].type.value
    types = {element.type for element in elements}
    if types <= _TEXT_FLOW_TYPES:
        return "paragraph"
    if ElementType.HEADING in types:
        return "heading"
    return elements[0].type.value


def _append_text_flow_group(
    flat: list[tuple[int, int, ParsedElement]],
    start: int,
) -> tuple[list[int], list[ParsedElement], str, int]:
    """从 start 起收集同页连续 paragraph/list_item。"""
    pg, idx, elem = flat[start]
    indices = [idx]
    elements = [elem]
    contents = [elem.text.strip()]
    bboxes: list[BoundingBox | None] = [elem.bbox]
    cursor = start + 1

    while cursor < len(flat):
        next_pg, next_idx, next_elem = flat[cursor]
        if next_pg != pg:
            break
        if next_elem.type not in _TEXT_FLOW_TYPES or not next_elem.text.strip():
            break
        indices.append(next_idx)
        elements.append(next_elem)
        contents.append(next_elem.text.strip())
        bboxes.append(next_elem.bbox)
        cursor += 1

    return indices, elements, "\n".join(contents), cursor


def split_evidence(bundle: ParsedBundle) -> list[EvidenceUnit]:
    """
    将 ParsedBundle 拆分为可引用的 EvidenceUnit 列表。

    拆分策略：
    1. 拍平所有页面的元素为单一列表
    2. heading 与其后紧跟的 paragraph 合并为一个单元
    3. 同页连续 paragraph/list_item 聚合为一个块级单元
    4. 跳过空文本元素；image/table/formula 单独成块
    """
    flat: list[tuple[int, int, ParsedElement]] = []
    for page in bundle.pages:
        for elem in page.elements:
            flat.append((page.page_number, len(flat), elem))

    units: list[EvidenceUnit] = []
    i = 0
    while i < len(flat):
        pg, idx, elem = flat[i]

        if elem.type == ElementType.IMAGE:
            artifact_ref = ""
            content = "[图片]"
            if elem.extra:
                md_url = elem.extra.get("url", "")
                if md_url:
                    content = md_url
                else:
                    artifact_ref = elem.extra.get("artifact_ref", "")
                    if elem.text and elem.text != "[图片]" and elem.text.strip():
                        content = elem.text

            units.append(
                EvidenceUnit(
                    bundle_id=bundle.id,
                    source_version_id=bundle.source_version_id,
                    content=content,
                    page_number=pg,
                    bbox=elem.bbox,
                    element_indices=[idx],
                    structure_type="image",
                    artifact_ref=artifact_ref,
                )
            )
            i += 1
            continue

        if not elem.text.strip():
            i += 1
            continue

        if elem.type == ElementType.HEADING:
            indices = [idx]
            elements = [elem]
            contents = [elem.text.strip()]
            bboxes: list[BoundingBox | None] = [elem.bbox]
            cursor = i + 1

            if cursor < len(flat):
                next_pg, next_idx, next_elem = flat[cursor]
                if (
                    next_pg == pg
                    and next_elem.type == ElementType.PARAGRAPH
                    and next_elem.text.strip()
                ):
                    indices.append(next_idx)
                    elements.append(next_elem)
                    contents.append(next_elem.text.strip())
                    bboxes.append(next_elem.bbox)
                    cursor += 1

            units.append(
                EvidenceUnit(
                    bundle_id=bundle.id,
                    source_version_id=bundle.source_version_id,
                    content="\n".join(contents),
                    page_number=pg,
                    bbox=_merge_bboxes(bboxes),
                    element_indices=indices,
                    structure_type=_structure_type_for_elements(elements),
                )
            )
            i = cursor
            continue

        if elem.type in _TEXT_FLOW_TYPES:
            indices, elements, content, cursor = _append_text_flow_group(flat, i)
            units.append(
                EvidenceUnit(
                    bundle_id=bundle.id,
                    source_version_id=bundle.source_version_id,
                    content=content,
                    page_number=pg,
                    bbox=_merge_bboxes([element.bbox for element in elements]),
                    element_indices=indices,
                    structure_type=_structure_type_for_elements(elements),
                )
            )
            i = cursor
            continue

        units.append(
            EvidenceUnit(
                bundle_id=bundle.id,
                source_version_id=bundle.source_version_id,
                content=elem.text.strip(),
                page_number=pg,
                bbox=elem.bbox,
                element_indices=[idx],
                structure_type=elem.type.value,
            )
        )
        i += 1

    return units
