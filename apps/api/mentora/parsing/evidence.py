"""
从 ParsedBundle 拆分 EvidenceUnit。

约定：
- 每个 paragraph / heading+paragraph 组合生成一个 EvidenceUnit
- heading 与其后第一个 paragraph 合并为一个证据单元（保留上下文）
- EvidenceUnit 通过 element_indices 引用 ParsedElement（0-based，拍平后索引）

约束：
- EvidenceUnit 不复制坐标数据
- 空白元素（text 为空）不生成 EvidenceUnit
- 每个 EvidenceUnit 必须有 page_number

@module mentora/parsing/evidence
"""

from mentora.parsing.schemas import ElementType, EvidenceUnit, Page, ParsedBundle


def split_evidence(bundle: ParsedBundle) -> list[EvidenceUnit]:
    """
    将 ParsedBundle 拆分为可引用的 EvidenceUnit 列表。

    拆分策略：
    1. 拍平所有页面的元素为单一列表
    2. heading 与其后紧跟的 paragraph 合并为一个单元
    3. 独立 paragraph 各自为一个单元
    4. 跳过 image 和空文本元素
    """
    # 1. 拍平元素
    flat: list[tuple[int, int, object]] = []  # (page_number, flat_index, element)
    for page in bundle.pages:
        for i, elem in enumerate(page.elements):
            flat.append((page.page_number, len(flat), elem))

    # 2. 按策略分组
    units: list[EvidenceUnit] = []
    i = 0
    while i < len(flat):
        pg, idx, elem = flat[i]

        # 图片 → 生成 EvidenceUnit，artifact_ref 指向对象存储中的图片
        if elem.type == ElementType.IMAGE:
            artifact_ref = ""
            if elem.extra:
                artifact_ref = elem.extra.get("artifact_ref", "")
                # 多模态描述替代占位文本
                if elem.text and elem.text != "[图片]" and elem.text.strip():
                    content = elem.text
                else:
                    content = "[图片]"
            else:
                content = "[图片]"

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

        # 跳过空文本
        if not elem.text.strip():
            i += 1
            continue

        # heading → 与下一个 paragraph 合并
        if elem.type == ElementType.HEADING and i + 1 < len(flat):
            next_pg, next_idx, next_elem = flat[i + 1]
            if next_elem.type == ElementType.PARAGRAPH and next_elem.text.strip():
                combined = elem.text + "\n" + next_elem.text
                units.append(
                    EvidenceUnit(
                        bundle_id=bundle.id,
                        source_version_id=bundle.source_version_id,
                        content=combined,
                        page_number=pg,
                        bbox=elem.bbox,
                        element_indices=[idx, next_idx],
                    )
                )
                i += 2
                continue

        # 普通 paragraph / 单独 heading
        units.append(
            EvidenceUnit(
                bundle_id=bundle.id,
                source_version_id=bundle.source_version_id,
                content=elem.text,
                page_number=pg,
                bbox=elem.bbox,
                element_indices=[idx],
            )
        )
        i += 1

    return units
