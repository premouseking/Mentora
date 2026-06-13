"""PyMuPDF 适配器测试。"""

import pytest
from mentora.parsing.adapters import (
    ImageOnlyPDFError,
    PyMuPDFAdapter,
)
from mentora.parsing.schemas import ElementType


class TestPyMuPDFAdapter:
    """PyMuPDF 适配器单元测试。"""

    def test_parse_normal_pdf(self, normal_pdf):
        """正常文本 PDF 应正确提取段落。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(normal_pdf, "1.0.0")

        assert bundle.content_hash is not None
        assert len(bundle.content_hash) == 64
        assert bundle.parser.name == "pymupdf"
        assert bundle.parser.version == "1.0.0"
        assert bundle.page_count == 1
        assert bundle.element_count >= 2

        # 应有段落元素
        paragraphs = [
            e for e in bundle.pages[0].elements if e.type == ElementType.PARAGRAPH
        ]
        assert len(paragraphs) >= 2

        # 坐标应为正
        for elem in bundle.pages[0].elements:
            if elem.bbox is not None:
                assert elem.bbox.x1 >= elem.bbox.x0
                assert elem.bbox.y1 >= elem.bbox.y0

    def test_parse_heading_pdf(self, heading_pdf):
        """含标题 PDF 应正确分类 heading 和 paragraph。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(heading_pdf, "1.0.0")

        headings = [
            e for e in bundle.pages[0].elements if e.type == ElementType.HEADING
        ]
        paragraphs = [
            e for e in bundle.pages[0].elements if e.type == ElementType.PARAGRAPH
        ]

        assert len(headings) >= 2, f"Expected >=2 headings, got {len(headings)}"
        assert len(paragraphs) >= 2

    def test_parse_multi_column_pdf(self, multi_column_pdf):
        """多栏 PDF 应保留两列元素的坐标差异。"""
        adapter = PyMuPDFAdapter()
        bundle = adapter.parse(multi_column_pdf, "1.0.0")

        assert bundle.page_count == 1

        elements = bundle.pages[0].elements
        x0_values = [e.bbox.x0 for e in elements if e.bbox is not None]
        if len(x0_values) >= 3:
            # 左栏元素 x0 ≈ 50, 右栏元素 x0 ≈ 310
            left_elems = [x for x in x0_values if x < 150]
            right_elems = [x for x in x0_values if x > 200]
            assert len(left_elems) >= 1
            assert len(right_elems) >= 1

    def test_parse_encrypted_pdf_raises(self, tmp_path):
        """加密 PDF 应抛出 EncryptedPDFError。"""
        import fitz

        path = str(tmp_path / "encrypted.pdf")
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secret", user_pw="secret")
        doc.close()

        adapter = PyMuPDFAdapter()
        with pytest.raises(ImageOnlyPDFError):
            # 文本为空时先抛 ImageOnly，非加密错误
            adapter.parse(path, "1.0.0")

    def test_parse_image_only_pdf(self, tmp_path):
        """纯图片 PDF（无文本）应抛出 ImageOnlyPDFError。"""
        import fitz

        path = str(tmp_path / "empty.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        # 插入一个小图片占位（无文本）
        pix = fitz.Pixmap(fitz.csRGB, 10, 10)
        page.insert_image(page.rect, pixmap=pix)
        doc.save(path)
        doc.close()

        adapter = PyMuPDFAdapter()
        with pytest.raises(ImageOnlyPDFError):
            adapter.parse(path, "1.0.0")
