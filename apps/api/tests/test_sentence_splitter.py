"""句子拆分单元测试。"""

from mentora.retrieval.sentence_splitter import (
    generate_sentence_projections,
    split_sentences,
)


class TestSplitSentences:
    """split_sentences() 纯函数测试。"""

    def test_simple_chinese(self):
        """中文句号拆分。"""
        result = split_sentences("直接映射是最简单的映射方式。每个主存块只能放入一个固定行。")
        assert len(result) == 2
        assert "直接映射" in result[0]
        assert "每个主存块" in result[1]

    def test_chinese_semicolon_and_newline(self):
        """分号和换行也应拆分。"""
        result = split_sentences("先做A；再做B。\n然后是C。")
        assert len(result) >= 3

    def test_keeps_english_period_in_decimal(self):
        """小数点和版本号不被误切。"""
        result = split_sentences("精度为0.95，版本v1.0。这是一句。")
        assert any("0.95" in s for s in result)
        assert any("v1.0" in s for s in result)

    def test_mixed_chinese_english(self):
        """中英混合句子。"""
        result = split_sentences("Cache 是非常快的存储器。It is much faster than main memory.")
        assert len(result) >= 2

    def test_empty_string(self):
        """空字符串返回空列表。"""
        result = split_sentences("")
        assert result == []

    def test_whitespace_only(self):
        """空白字符串返回空列表。"""
        result = split_sentences("   \n  ")
        assert result == []

    def test_merges_short_fragments(self):
        """过短片段合并到下一句。"""
        result = split_sentences("好。这是一个完整的测试句子。")
        assert len(result) == 2
        assert "好。" in result[0] or result[0].startswith("好")


class TestGenerateProjections:
    """generate_sentence_projections() 测试。"""

    def test_generates_correct_count(self):
        """应生成与句子数相等的 Projection。"""
        projections = generate_sentence_projections(
            "00000000-0000-0000-0000-000000000001",
            "第一句。第二句。第三句。",
        )
        assert len(projections) == 3
        assert projections[0].position_index == 0
        assert projections[0].content == "第一句。"
        assert projections[2].position_index == 2

    def test_filters_empty_sentences(self):
        """空内容返回空列表。"""
        projections = generate_sentence_projections(
            "00000000-0000-0000-0000-000000000002",
            "",
        )
        assert projections == []
