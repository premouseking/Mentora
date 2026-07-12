"""EvidenceUnit 块级聚合测试。"""

from uuid import uuid4

from django.test import SimpleTestCase

from mentora.parsing.evidence import split_evidence
from mentora.parsing.schemas import (
    BoundingBox,
    ElementType,
    Page,
    ParsedBundle,
    ParsedElement,
    ParserInfo,
)


def _bbox(x0: float, y0: float, x1: float, y1: float) -> BoundingBox:
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _bundle(*pages: Page) -> ParsedBundle:
    return ParsedBundle(
        id=uuid4(),
        source_version_id="sv-test",
        parser=ParserInfo(name="test", version="1.0"),
        content_hash="a" * 64,
        pages=list(pages),
    )


class SplitEvidenceTests(SimpleTestCase):
    def test_merges_consecutive_paragraphs_on_same_page(self):
        bundle = _bundle(
            Page(
                page_number=1,
                elements=[
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="第一句。",
                        bbox=_bbox(10, 80, 90, 90),
                    ),
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="第二句。",
                        bbox=_bbox(10, 60, 90, 70),
                    ),
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="第三句。",
                        bbox=_bbox(10, 40, 90, 50),
                    ),
                ],
            ),
        )

        units = split_evidence(bundle)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].element_indices, [0, 1, 2])
        self.assertIn("第一句", units[0].content)
        self.assertIn("第三句", units[0].content)
        self.assertEqual(units[0].bbox.x0, 10)
        self.assertEqual(units[0].bbox.y0, 40)
        self.assertEqual(units[0].bbox.x1, 90)
        self.assertEqual(units[0].bbox.y1, 90)

    def test_merges_list_items_with_paragraphs(self):
        bundle = _bundle(
            Page(
                page_number=1,
                elements=[
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="说明段落。",
                        bbox=_bbox(0, 70, 100, 80),
                    ),
                    ParsedElement(
                        type=ElementType.LIST_ITEM,
                        text="列表项一",
                        bbox=_bbox(0, 50, 100, 60),
                    ),
                    ParsedElement(
                        type=ElementType.LIST_ITEM,
                        text="列表项二",
                        bbox=_bbox(0, 30, 100, 40),
                    ),
                ],
            ),
        )

        units = split_evidence(bundle)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].element_indices, [0, 1, 2])

    def test_does_not_merge_across_pages(self):
        bundle = _bundle(
            Page(
                page_number=1,
                elements=[
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="第一页",
                        bbox=_bbox(0, 10, 10, 20),
                    ),
                ],
            ),
            Page(
                page_number=2,
                elements=[
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="第二页",
                        bbox=_bbox(0, 10, 10, 20),
                    ),
                ],
            ),
        )

        units = split_evidence(bundle)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0].element_indices, [0])
        self.assertEqual(units[1].element_indices, [1])

    def test_heading_merges_with_following_paragraph_only(self):
        bundle = _bundle(
            Page(
                page_number=1,
                elements=[
                    ParsedElement(
                        type=ElementType.HEADING,
                        text="标题",
                        bbox=_bbox(0, 90, 100, 100),
                        heading_level=2,
                    ),
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="标题下第一段",
                        bbox=_bbox(0, 70, 100, 80),
                    ),
                    ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="后续段落",
                        bbox=_bbox(0, 50, 100, 60),
                    ),
                ],
            ),
        )

        units = split_evidence(bundle)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0].element_indices, [0, 1])
        self.assertEqual(units[1].element_indices, [2])
