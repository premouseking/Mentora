"""ChunkProjection 生成器测试。"""

from dataclasses import dataclass

from mentora.retrieval.chunk_builder import build_chunks, estimate_tokens


@dataclass
class _FakeEvidence:
    id: str
    content: str
    source_version_id: str = "sv-1"


class TestEstimateTokens:
    """Token 估算测试。"""

    def test_pure_chinese(self):
        """纯中文估算。"""
        tokens = estimate_tokens("计算机系统由硬件和软件两部分组成")
        assert tokens >= 5

    def test_mixed_chinese_english(self):
        """中英混合估算 > 纯中文。"""
        cn = estimate_tokens("计算机系统")
        mixed = estimate_tokens("计算机 system")
        assert mixed >= cn

    def test_short_text_min_one(self):
        """短文本至少返回 1。"""
        assert estimate_tokens("A") == 1
        assert estimate_tokens("中") == 1


class TestBuildChunks:
    """Chunk 生成测试。"""

    def test_single_unit(self):
        """单个 EvidenceUnit → 1 个 Chunk。"""
        units = [_FakeEvidence(id="e1", content="这是一段内容。")]
        chunks = build_chunks(units)
        assert len(chunks) == 1
        assert chunks[0].evidence_ids == ["e1"]

    def test_multiple_small_units_one_chunk(self):
        """多个小 unit 合并为 1 个 Chunk。"""
        units = [
            _FakeEvidence(id=f"e{i}", content="短内容。")
            for i in range(5)
        ]
        chunks = build_chunks(units)
        assert len(chunks) == 1
        assert len(chunks[0].evidence_ids) == 5

    def test_large_units_split(self):
        """超过 chunk_size 时拆分。"""
        # 每个 ~100 token，chunk_size=200 → 每 2 个一组
        units = [
            _FakeEvidence(id="e1", content="内容。" * 80),   # ~100 tokens
            _FakeEvidence(id="e2", content="内容。" * 80),
            _FakeEvidence(id="e3", content="内容。" * 80),
            _FakeEvidence(id="e4", content="内容。" * 80),
        ]
        chunks = build_chunks(units, chunk_size=200)
        assert len(chunks) >= 2

    def test_overlap_between_chunks(self):
        """相邻 Chunk 有重叠 EvidenceUnit。"""
        # 每个 unit ~25 tokens, chunk_size=80 → 每 chunk 装 3 个 unit, 重叠 1 个
        units = [
            _FakeEvidence(id=f"e{i}", content="短内容。" * 8)
            for i in range(6)
        ]
        chunks = build_chunks(units, chunk_size=80, overlap=1)
        assert len(chunks) >= 2

        # 第 1 个 Chunk 的最后一个 ID 应 = 第 2 个 Chunk 的第一个 ID
        last_of_first = chunks[0].evidence_ids[-1]
        first_of_second = chunks[1].evidence_ids[0]
        assert last_of_first == first_of_second, \
            f"Overlap missing: {last_of_first} != {first_of_second}"

    def test_empty_list(self):
        """空列表返回空。"""
        assert build_chunks([]) == []

    def test_chunk_content_preserved(self):
        """Chunk content 是原始内容拼接。"""
        units = [
            _FakeEvidence(id="e1", content="第一段。"),
            _FakeEvidence(id="e2", content="第二段。"),
        ]
        chunks = build_chunks(units, chunk_size=500)
        assert "第一段。" in chunks[0].content
        assert "第二段。" in chunks[0].content
