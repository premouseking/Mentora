"""语义块扩展与检索结果回归测试。"""

import uuid
from dataclasses import dataclass
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from mentora.agent_runtime.agents.turn_loop import (
    _extract_tool_citations,
    _format_tool_message_content,
)
from mentora.retrieval.models import ChunkProjection, EvidenceUnit
from mentora.retrieval.search import SearchResult, _apply_semantic_blocks
from mentora.retrieval.semantic_blocks import (
    _expand_adjacent_on_page,
    expand_evidence_units_to_blocks,
)


@dataclass
class _FakeUnit:
    id: str
    content: str
    source_version_id: str = "sv-1"
    page_number: int = 1
    element_indices: list | None = None
    structure_type: str = "paragraph"


class AdjacentExpansionTests(SimpleTestCase):
    def test_merges_fragment_units_on_same_page(self):
        units = [
            _FakeUnit("u1", "进程。", element_indices=[0]),
            _FakeUnit("u2", "进程的组织结构包括代码段、数据段和堆栈。", element_indices=[1]),
            _FakeUnit("u3", "一个进程所请求的系统资源由操作系统统一分配。", element_indices=[2]),
        ]
        content, count = _expand_adjacent_on_page(units[1], units)
        self.assertEqual(count, 3)
        self.assertIn("进程。", content)
        self.assertIn("进程的组织结构", content)
        self.assertIn("一个进程所请求", content)

    def test_stops_at_heading_boundary(self):
        units = [
            _FakeUnit("u1", "上一节内容。", element_indices=[0]),
            _FakeUnit("u2", "短句。", element_indices=[1]),
            _FakeUnit("u3", "新章节", element_indices=[2], structure_type="heading"),
            _FakeUnit("u4", "新章节正文。", element_indices=[3]),
        ]
        content, count = _expand_adjacent_on_page(units[1], units)
        self.assertEqual(count, 2)
        self.assertIn("上一节内容", content)
        self.assertIn("短句", content)
        self.assertNotIn("新章节正文", content)


class SemanticBlockIntegrationTests(TestCase):
    def setUp(self):
        self.sv_id = "sv-test-semantic"
        self.unit_ids = [uuid.uuid4() for _ in range(3)]
        EvidenceUnit.objects.bulk_create([
            EvidenceUnit(
                id=self.unit_ids[0],
                source_version_id=self.sv_id,
                bundle_id=uuid.uuid4(),
                content="进程。",
                page_number=2,
                element_indices=[0],
                structure_type="paragraph",
            ),
            EvidenceUnit(
                id=self.unit_ids[1],
                source_version_id=self.sv_id,
                bundle_id=uuid.uuid4(),
                content="进程的组织结构，",
                page_number=2,
                element_indices=[1],
                structure_type="paragraph",
            ),
            EvidenceUnit(
                id=self.unit_ids[2],
                source_version_id=self.sv_id,
                bundle_id=uuid.uuid4(),
                content="一个进程所请求的系统资源由操作系统统一分配。",
                page_number=2,
                element_indices=[2],
                structure_type="paragraph",
            ),
        ])

    def test_prefers_chunk_projection_content(self):
        ChunkProjection.objects.create(
            source_version_id=self.sv_id,
            evidence_ids=[str(uid) for uid in self.unit_ids],
            content="进程。\n\n进程的组织结构，\n\n一个进程所请求的系统资源由操作系统统一分配。",
            token_count=40,
        )
        anchor = EvidenceUnit.objects.get(id=self.unit_ids[0])
        blocks = expand_evidence_units_to_blocks([anchor])
        block = blocks[str(anchor.id)]
        self.assertEqual(block.block_evidence_count, 3)
        self.assertIn("进程的组织结构", block.content)
        self.assertIn("一个进程所请求", block.content)

    def test_falls_back_to_adjacent_expansion_without_chunk(self):
        anchor = EvidenceUnit.objects.get(id=self.unit_ids[1])
        blocks = expand_evidence_units_to_blocks([anchor])
        block = blocks[str(anchor.id)]
        self.assertGreaterEqual(block.block_evidence_count, 2)
        self.assertIn("进程。", block.content)
        self.assertIn("一个进程所请求", block.content)

    def test_search_result_to_dict_uses_semantic_content(self):
        anchor = EvidenceUnit.objects.get(id=self.unit_ids[0])
        result = SearchResult(
            evidence=SimpleNamespace(
                id=str(anchor.id),
                content=anchor.content,
                page_number=anchor.page_number,
            ),
            score=0.9,
        )
        expanded = _apply_semantic_blocks([result], source_version_ids=[self.sv_id])[0]
        payload = expanded.to_dict()
        self.assertIn("进程的组织结构", payload["content"])
        self.assertGreater(payload["block_evidence_count"], 1)
        self.assertEqual(payload["matched_preview"], "进程。")


class FragmentCitationRegressionTests(SimpleTestCase):
    def test_tool_message_and_citations_hide_evidence_id_with_merged_content(self):
        merged = (
            "进程。\n\n"
            "进程的组织结构，\n\n"
            "一个进程所请求的系统资源由操作系统统一分配。"
        )
        result = SimpleNamespace(
            tool_name="retrieve_evidence",
            success=True,
            result={
                "query": "进程",
                "results": [
                    {
                        "evidence_id": "secret-evidence-id",
                        "content": merged,
                        "content_preview": merged[:200],
                        "page_number": 2,
                        "source_title": "操作系统讲义",
                        "block_evidence_count": 3,
                    }
                ],
            },
            error="",
            artifact_ref="",
        )

        tool_message = _format_tool_message_content(result)
        citations = _extract_tool_citations(result)

        self.assertNotIn("evidence_id", tool_message)
        self.assertNotIn("secret-evidence-id", tool_message)
        self.assertIn("进程的组织结构", tool_message)
        self.assertEqual(len(citations), 1)
        self.assertNotIn("evidence_id", citations[0])
        self.assertEqual(citations[0]["content"], merged)
        self.assertEqual(citations[0]["source_title"], "操作系统讲义")
