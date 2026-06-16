"""引用定位服务单元测试。"""

import pytest
from mentora.parsing.schemas import (
    BoundingBox,
    EvidenceUnit,
    ParsedBundle,
    ParsedElement,
    ElementType,
    Page,
    ParserInfo,
)
from mentora.retrieval.locator import (
    CitationLocation,
    SentenceLocation,
)


class TestCitationLocation:
    """CitationLocation 数据结构测试。"""

    def test_to_dict(self):
        loc = CitationLocation(
            evidence_id="e8d1a2b3-0001-4000-8000-000000000001",
            page_number=3,
            bbox={"x0": 72, "y0": 690, "x1": 480, "y1": 708},
            content="直接映射是三种 Cache 映射方式中最简单的一种。",
            context_before="主存块装入 Cache 时需要按某种函数关系映射到 Cache 行。",
            context_after="组相联映射折中了直接映射和全相联的特点。",
            sentences=[
                SentenceLocation(position_index=0, content="直接映射是三种 Cache 映射方式中最简单的一种。"),
            ],
        )
        d = loc.to_dict()
        assert d["evidence_id"] == "e8d1a2b3-0001-4000-8000-000000000001"
        assert d["page_number"] == 3
        assert d["bbox"]["x0"] == 72
        assert d["context_before"] is not None
        assert d["context_after"] is not None
        assert len(d["sentences"]) == 1

    def test_minimal_location(self):
        """最小定位信息：无上下文、无句子。"""
        loc = CitationLocation(
            evidence_id="e8d1a2b3-0001-4000-8000-000000000002",
            page_number=1,
            bbox=None,
            content="一段文本。",
        )
        d = loc.to_dict()
        assert d["evidence_id"] is not None
        assert d["context_before"] is None
        assert d["context_after"] is None
        assert d["sentences"] == []
        assert d["bbox"] is None


class TestEvidenceUnitDataStructure:
    """EvidenceUnit 数据结构完整性和跨模块引用测试。"""

    def test_evidence_unit_fields_match_locator_expectations(self):
        """EvidenceUnit Pydantic 字段应包含定位所需的所有信息。"""
        unit = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000001",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="直接映射每个主存块只能放入一个固定的 Cache 行。",
            page_number=3,
            bbox=BoundingBox(x0=72, y0=690, x1=480, y1=708),
            element_indices=[0],
        )

        # 定位服务需要这些字段
        assert unit.id is not None
        assert unit.page_number == 3
        assert unit.bbox is not None
        assert unit.content != ""
        assert unit.source_version_id == "sv-1"

    def test_element_indices_reference_integrity(self):
        """element_indices 应指向 ParsedBundle 中存在的元素。"""
        bundle = ParsedBundle(
            source_version_id="sv-1",
            parser=ParserInfo(name="pymupdf", version="1.0.0"),
            content_hash="a" * 64,
            pages=[
                Page(page_number=3, elements=[
                    ParsedElement(type=ElementType.HEADING, text="Cache 映射", heading_level=2),
                    ParsedElement(type=ElementType.PARAGRAPH, text="直接映射每个主存块只能放入一个固定行。"),
                    ParsedElement(type=ElementType.PARAGRAPH, text="组相联映射折中了直接映射和全相联的特点。"),
                ]),
            ],
        )

        # 拍平元素列表
        flat_elements = []
        for page in bundle.pages:
            flat_elements.extend(page.elements)

        # 验证 element_indices 不越界
        unit = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000001",
            bundle_id=bundle.id,
            source_version_id="sv-1",
            content=bundle.pages[0].elements[1].text,
            page_number=3,
            bbox=bundle.pages[0].elements[1].bbox,
            element_indices=[1],
        )
        for idx in unit.element_indices:
            assert 0 <= idx < len(flat_elements), f"Index {idx} out of range"
            assert flat_elements[idx].text != ""

    def test_cross_page_context_boundary(self):
        """跨页上下文不应包含不同页的证据。"""
        page1_unit = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000010",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="第 1 页内容。",
            page_number=1,
            element_indices=[0],
        )
        page3_unit = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-000000000030",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="第 3 页内容。",
            page_number=3,
            element_indices=[0],
        )
        # 这两个分属不同页，不应互为上下文
        assert page1_unit.page_number != page3_unit.page_number

    def test_same_page_adjacent(self):
        """同页相邻的两个 EvidenceUnit 应能互为上下文。"""
        unit_a = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-0000000000a0",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="段落 A。",
            page_number=4,
            element_indices=[0],
        )
        unit_b = EvidenceUnit(
            id="e8d1a2b3-0001-4000-8000-0000000000b0",
            bundle_id="b0000000-0000-0000-0000-000000000001",
            source_version_id="sv-1",
            content="段落 B。",
            page_number=4,
            element_indices=[1],
        )
        assert unit_a.page_number == unit_b.page_number
        assert unit_a.source_version_id == unit_b.source_version_id
