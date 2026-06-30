"""
多列 PDF 阅读顺序恢复。

约定：
- 输入为单页已提取的 ParsedElement 列表（按 PyMuPDF 物理顺序）
- 通过 x0 值最大间隙检测分栏
- 每栏内按 y0 降序排列（PDF 左下角原点，y 越大 = 越靠页面顶部）
- 单栏或无法分栏时保持原序

约束：
- 不回退 coordinate-less 元素的顺序
- 超过 2 栏时标记警告，尽力按栏序输出

@module mentora/parsing/adapters/column_reorder
"""

from mentora.parsing.schemas import ParsedElement


def _find_split_point(x0_values: list[float], page_width: float) -> float | None:
    """
    在 x0 值列表中找到最大自然间隙的中点作为分栏点。

    返回 None 表示间隙不够大，视为单栏。
    """
    unique = sorted(set(x0_values))
    if len(unique) < 2:
        return None

    max_gap = 0.0
    split_at = unique[0]
    for i in range(len(unique) - 1):
        gap = unique[i + 1] - unique[i]
        if gap > max_gap:
            max_gap = gap
            split_at = (unique[i] + unique[i + 1]) / 2.0

    # 间隙需超过页宽 5% 才视为有效分栏
    if max_gap < page_width * 0.05:
        return None
    return split_at


def reorder_elements(
    elements: list[ParsedElement],
    page_width: float,
) -> tuple[list[ParsedElement], list[str]]:
    """
    对单页元素按阅读顺序重排，返回 (重排后列表, 警告列表)。

    参数：
        elements: 当前物理顺序的元素列表
        page_width: 页面宽度（pt），用于判断分栏显著性
    """
    if len(elements) < 2:
        return list(elements), []

    # 收集有 bbox 的元素的 x0
    x0_values = [el.bbox.x0 for el in elements if el.bbox is not None]
    if len(x0_values) < 2:
        return list(elements), []

    # 判断是否多栏：x0 跨度超过页面宽度的 30%
    x0_range = max(x0_values) - min(x0_values)
    if x0_range < page_width * 0.3:
        return list(elements), []

    split_point = _find_split_point(x0_values, page_width)
    if split_point is None:
        return list(elements), []

    left: list[ParsedElement] = []
    right: list[ParsedElement] = []
    no_bbox: list[ParsedElement] = []

    for el in elements:
        if el.bbox is None:
            no_bbox.append(el)
        elif el.bbox.x0 < split_point:
            left.append(el)
        else:
            right.append(el)

    if not left or not right:
        return list(elements), []

    # 每栏内按 y0 降序（PDF 坐标系：y 越大越靠上 → 阅读顺序从上到下）
    left.sort(key=lambda el: el.bbox.y0 if el.bbox else 0, reverse=True)
    right.sort(key=lambda el: el.bbox.y0 if el.bbox else 0, reverse=True)

    warnings: list[str] = []
    # 检查是否有更多栏（右栏内部再分）
    right_x0s = [el.bbox.x0 for el in right if el.bbox is not None]
    if right_x0s:
        right_unique = sorted(set(right_x0s))
        if len(right_unique) >= 2:
            inner_max_gap = max(
                right_unique[i + 1] - right_unique[i]
                for i in range(len(right_unique) - 1)
            )
            if inner_max_gap > page_width * 0.15:
                warnings.append(
                    "检测到 2 栏以上布局，按左→右顺序尽力输出，"
                    "复杂排版的阅读顺序可能不完全正确"
                )

    result = left + right + no_bbox
    return result, warnings
