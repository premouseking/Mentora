"""EvidenceUnit 拆分测试。"""

from mentora.parsing.evidence import split_evidence
from mentora.parsing.schemas import (
    BoundingBox,
    ElementType,
    Page,
    ParsedBundle,
    ParsedElement,
    ParserInfo,
)


def _make_bundle(pages: list[Page]) -> ParsedBundle:
    return ParsedBundle(
        source_version_id="sv-test",
        parser=ParserInfo(name="pymupdf", version="1.0.0"),
        content_hash="a" * 64,
        pages=pages,
    )


class TestSplitEvidence:
    """EvidenceUnit 拆分单元测试。"""

    def test_single_paragraph(self):
        """单个 paragraph 应生成一个 EvidenceUnit。"""
        page = Page(
            page_number=1,
            elements=[
                ParsedElement(type=ElementType.PARAGRAPH, text="这是一段正文。"),
            ],
        )
        bundle = _make_bundle([page])
        units = split_evidence(bundle)

        assert len(units) == 1
        assert units[0].content == "这是一段正文。"
        assert units[0].page_number == 1
        assert units[0].element_indices == [0]
        assert units[0].bundle_id == bundle.id

    def test_heading_merged_with_paragraph(self):
        """heading + paragraph 应合并为一个 EvidenceUnit。"""
        page = Page(
            page_number=1,
            elements=[
                ParsedElement(
                    type=ElementType.HEADING, text="第三章", heading_level=1
                ),
                ParsedElement(
                    type=ElementType.PARAGRAPH, text="存储器是计算机的核心部件。"
                ),
            ],
        )
        bundle = _make_bundle([page])
        units = split_evidence(bundle)

        assert len(units) == 1
        assert "第三章" in units[0].content
        assert "存储器" in units[0].content
        assert units[0].element_indices == [0, 1]

    def test_heading_alone(self):
        """单独 heading（无后续 paragraph 或后续非 paragraph）不合并。"""
        page = Page(
            page_number=1,
            elements=[
                ParsedElement(
                    type=ElementType.HEADING, text="孤立的标题", heading_level=1
                ),
                ParsedElement(
                    type=ElementType.HEADING, text="另一个标题", heading_level=2
                ),
            ],
        )
        bundle = _make_bundle([page])
        units = split_evidence(bundle)

        assert len(units) == 2
        assert units[0].content == "孤立的标题"
        assert units[1].content == "另一个标题"

    def test_skips_images(self):
        """图片元素应被跳过。"""
        page = Page(
            page_number=1,
            elements=[
                ParsedElement(type=ElementType.PARAGRAPH, text="正文前。"),
                ParsedElement(type=ElementType.IMAGE, text=""),
                ParsedElement(type=ElementType.PARAGRAPH, text="正文后。"),
            ],
        )
        bundle = _make_bundle([page])
        units = split_evidence(bundle)

        assert len(units) == 2
        assert units[0].content == "正文前。"
        assert units[1].content == "正文后。"

    def test_multi_page(self):
        """多页文档应正确标注页码。"""
        pages = [
            Page(
                page_number=1,
                elements=[
                    ParsedElement(type=ElementType.PARAGRAPH, text="第一页内容。"),
                ],
            ),
            Page(
                page_number=2,
                elements=[
                    ParsedElement(type=ElementType.PARAGRAPH, text="第二页内容。"),
                ],
            ),
        ]
        bundle = _make_bundle(pages)
        units = split_evidence(bundle)

        assert len(units) == 2
        assert units[0].page_number == 1
        assert units[1].page_number == 2
