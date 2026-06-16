"""表格提取测试。"""

import os
import tempfile

import fitz
import pytest

from mentora.parsing.adapters.pymupdf import PyMuPDFAdapter
from mentora.parsing.schemas import ElementType


def _make_table_pdf(path: str) -> None:
    """生成含原生线条表格的 PDF。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # 表格区域
    x0, y0 = 72, 600
    cols = 3
    rows = 3
    cw = 150
    rh = 30

    # 画表格线
    for i in range(rows + 1):
        y = y0 + i * rh
        page.draw_line(fitz.Point(x0, y), fitz.Point(x0 + cols * cw, y))
    for j in range(cols + 1):
        x = x0 + j * cw
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y0 + rows * rh))

    # 写入表头和数据
    data = [
        ["姓名", "成绩", "排名"],
        ["张三", "95", "1"],
        ["李四", "87", "2"],
    ]
    for ri, row in enumerate(data):
        for ci, cell in enumerate(row):
            x = x0 + ci * cw + 5
            y = y0 + ri * rh + 20
            page.insert_text(fitz.Point(x, y), cell, fontsize=10)

    # 表格后的正文
    page.insert_text(fitz.Point(72, 520), "以上是本次考试成绩汇总。", fontsize=11)

    doc.save(path)
    doc.close()


@pytest.fixture(scope="module")
def table_pdf():
    """含表格的 PDF fixture。"""
    path = os.path.join(tempfile.gettempdir(), "test_table.pdf")
    if not os.path.exists(path):
        _make_table_pdf(path)
    return path


class TestTableExtraction:
    """表格检测与提取测试。"""

    def test_no_table_in_normal_pdf(self):
        """非表格 PDF 不应产生 TABLE 类型元素。"""
        adapter = PyMuPDFAdapter()
        # 使用 fixtures 目录中的 normal.pdf
        fixtures_dir = os.path.join(
            os.path.dirname(__file__), "fixtures"
        )
        normal = os.path.join(fixtures_dir, "normal.pdf")
        if not os.path.exists(normal):
            pytest.skip("fixtures/normal.pdf 不存在")

        bundle = adapter.parse(normal, "1.0.0")
        all_types = set()
        for page in bundle.pages:
            for el in page.elements:
                all_types.add(el.type)
        assert ElementType.TABLE not in all_types

    def test_table_detected(self, table_pdf):
        """含原生线的表格应被检测为 TABLE 元素。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(table_pdf, "1.0.0")
        table_elements = [
            el for page in bundle.pages
            for el in page.elements
            if el.type == ElementType.TABLE
        ]
        assert len(table_elements) >= 1, f"未检测到表格，元素类型: {[el.type for p in bundle.pages for el in p.elements]}"

    def test_table_has_tsv_text(self, table_pdf):
        """表格元素的 text 应为 TSV 格式。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(table_pdf, "1.0.0")
        table_el = next(
            (el for page in bundle.pages for el in page.elements
             if el.type == ElementType.TABLE),
            None,
        )
        if table_el is None:
            pytest.skip("未检测到表格")
        # TSV 格式：制表符分隔 + 换行
        assert "\t" in table_el.text or "TSV" in table_el.text

    def test_table_has_bbox(self, table_pdf):
        """表格元素应有 bbox。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(table_pdf, "1.0.0")
        table_el = next(
            (el for page in bundle.pages for el in page.elements
             if el.type == ElementType.TABLE),
            None,
        )
        if table_el is None:
            pytest.skip("未检测到表格")
        assert table_el.bbox is not None


class TestTableEdgeCases:
    """表格提取边界情况。"""

    def test_parse_with_table_does_not_crash(self, table_pdf):
        """含表格 PDF 解析不应崩溃。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(table_pdf, "1.0.0")
        assert bundle is not None
        assert bundle.pages is not None

    def test_table_does_not_duplicate_content(self, table_pdf):
        """表格内容不应在 TABLE 元素之外重复出现。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(table_pdf, "1.0.0")
        for page in bundle.pages:
            for el in page.elements:
                # 非表格元素不应包含 TSV 标记
                if el.type not in (ElementType.TABLE, ElementType.IMAGE):
                    assert "TSV(" not in el.text, \
                        f"非表格元素包含了 TSV 内容: {el.text[:50]}"
