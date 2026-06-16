"""多列阅读顺序恢复测试。"""

from mentora.parsing.adapters.column_reorder import reorder_elements
from mentora.parsing.schemas import BoundingBox, ElementType, ParsedElement


# A4 宽度，pt
A4_WIDTH = 595.0


def _el(x0: float, y0: float, x1: float, y1: float, text: str = "x") -> ParsedElement:
    return ParsedElement(
        type=ElementType.PARAGRAPH,
        text=text,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
    )


class TestSingleColumn:
    """单栏文档不重排。"""

    def test_similar_x0_preserves_order(self):
        """x0 集中时保持原序。"""
        elements = [
            _el(60, 700, 500, 720, "第一段"),  # 顶部
            _el(60, 660, 500, 680, "第二段"),  # 中部
            _el(60, 620, 500, 640, "第三段"),  # 底部
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        assert [e.text for e in result] == ["第一段", "第二段", "第三段"]
        assert warnings == []

    def test_narrow_range_no_split(self):
        """x0 跨度 < 30% 页宽时视为单栏。"""
        # 所有元素 x0 在 200-300 之间，跨度 100pt < 178pt (30% * 595)
        elements = [
            _el(200, 700, 280, 720, "左偏上"),
            _el(250, 660, 330, 680, "稍右中"),
            _el(220, 620, 300, 640, "左偏下"),
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        assert len(result) == 3
        assert warnings == []


class TestTwoColumn:
    """双栏文档重排。"""

    def test_left_then_right(self):
        """左栏完整在前，右栏在后。"""
        # 模拟双栏布局：左栏 x0≈50，右栏 x0≈320
        elements = [
            _el(320, 400, 520, 420, "右栏1"),  # 物理顺序：右栏在上
            _el(50, 700, 250, 720, "左栏1"),   # 左栏顶部
            _el(50, 660, 250, 680, "左栏2"),   # 左栏中部
            _el(320, 360, 520, 380, "右栏2"),  # 右栏中部
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        texts = [e.text for e in result]
        # 左栏完整 → 右栏完整；栏内 y0 降序
        assert texts == ["左栏1", "左栏2", "右栏1", "右栏2"], f"Got: {texts}"
        assert warnings == []

    def test_small_gap_treated_as_single(self):
        """栏间间隙过小视为单栏。"""
        # 间隙仅 5pt，< 30pt (5% * 595)
        elements = [
            _el(50, 700, 200, 720, "左"),
            _el(205, 660, 350, 680, "右"),
            _el(55, 620, 200, 640, "左下"),
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        assert len(result) == 3
        assert warnings == []


class TestThreeColumn:
    """三栏及以上：尽力输出 + 警告。"""

    def test_three_columns_warns(self):
        """三栏产生警告。"""
        elements = [
            _el(50, 700, 150, 720, "栏1"),
            _el(220, 700, 320, 720, "栏2"),
            _el(390, 700, 490, 720, "栏3"),
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        assert len(result) == 3
        assert any("2 栏以上" in w for w in warnings)


class TestEdgeCases:
    """边界情况。"""

    def test_empty_list(self):
        elements, warnings = reorder_elements([], A4_WIDTH)
        assert elements == []
        assert warnings == []

    def test_single_element(self):
        el = _el(50, 700, 200, 720, "唯一")
        result, warnings = reorder_elements([el], A4_WIDTH)
        assert len(result) == 1
        assert result[0].text == "唯一"
        assert warnings == []

    def test_no_bbox_elements_at_end(self):
        """无 bbox 的元素保持原序追加到末尾。"""
        no_bbox = ParsedElement(type=ElementType.PARAGRAPH, text="无坐标")
        elements = [
            _el(320, 400, 520, 420, "右"),
            _el(50, 700, 250, 720, "左"),
            no_bbox,
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        # 无 bbox 的元素应在末尾
        assert result[-1].text == "无坐标"
        assert warnings == []

    def test_y0_descending_within_column(self):
        """栏内按 y0 降序排列（页面上方在前）。"""
        elements = [
            _el(50, 620, 200, 640, "左底部"),
            _el(50, 700, 200, 720, "左顶部"),
            _el(50, 660, 200, 680, "左中部"),
            _el(350, 660, 500, 680, "右中部"),
            _el(350, 700, 500, 720, "右顶部"),
        ]
        result, warnings = reorder_elements(elements, A4_WIDTH)
        left_texts = [e.text for e in result if "左" in e.text]
        right_texts = [e.text for e in result if "右" in e.text]
        assert left_texts == ["左顶部", "左中部", "左底部"]
        assert right_texts == ["右顶部", "右中部"]
        assert warnings == []
