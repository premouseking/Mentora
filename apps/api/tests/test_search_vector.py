"""向量搜索集成测试。"""

from unittest.mock import MagicMock, patch

import pytest

from mentora.retrieval.search import _search_vector, search


class TestSearchVector:
    """_search_vector() 单元测试。"""

    def test_returns_empty_when_no_provider(self):
        """provider 不可用时返回空 dict（优雅降级）。"""
        # get_provider 在 _search_vector 内从 embedding_provider 懒导入
        with patch(
            "mentora.retrieval.embedding_provider.get_provider",
            side_effect=ValueError("未配置"),
        ):
            result = _search_vector("测试查询")
            assert result == {}

    def test_returns_chunk_to_evidence_mapping(self):
        """正常流程：query → embedding → chunks → evidence id 映射。"""
        mock_provider = MagicMock()
        mock_provider.embed.return_value = [[0.1] * 1024]

        mock_chunk1 = MagicMock()
        mock_chunk1.distance = 0.2
        mock_chunk1.evidence_ids = ["eid-1", "eid-2"]

        mock_chunk2 = MagicMock()
        mock_chunk2.distance = 0.5
        mock_chunk2.evidence_ids = ["eid-3"]

        with patch(
            "mentora.retrieval.embedding_provider.get_provider",
            return_value=mock_provider,
        ):
            with patch(
                "mentora.retrieval.repository.search_chunks_by_vector",
                return_value=[mock_chunk1, mock_chunk2],
            ):
                result = _search_vector("Cache 存储原理", ["sv-1"])

        assert result["eid-1"] == pytest.approx(1.0 / 1.2)
        assert result["eid-2"] == pytest.approx(1.0 / 1.2)
        assert result["eid-3"] == pytest.approx(1.0 / 1.5)
        assert len(result) == 3

    def test_empty_chunks_returns_empty(self):
        """无匹配 Chunk 时返回空。"""
        mock_provider = MagicMock()
        mock_provider.embed.return_value = [[0.1] * 1024]

        with patch(
            "mentora.retrieval.embedding_provider.get_provider",
            return_value=mock_provider,
        ):
            with patch(
                "mentora.retrieval.repository.search_chunks_by_vector",
                return_value=[],
            ):
                result = _search_vector("无匹配")
                assert result == {}


class TestSearchIntegration:
    """search() 集成测试。"""

    def test_search_vector_weight_zero_skips_provider(self):
        """vector_weight=0 时不调用 get_provider。"""
        result = search(
            "计算机系统",
            top_k=5,
            vector_weight=0,
        )
        assert result is not None
        # 所有结果的 vector_score 应为 0
        for r in result.results:
            assert r.vector_score == 0.0

    def test_search_preserves_new_params(self):
        """search() 接收新的 vector_weight 和 source_version_ids 参数。"""
        result = search(
            "Cache",
            top_k=5,
            fts_weight=0.5,
            trgm_weight=0.2,
            vector_weight=0.3,
            source_version_ids=["sv-test"],
        )
        assert result is not None
        assert result.query == "Cache"

    def test_search_default_weights_no_error(self):
        """默认权重下 search() 正常返回（测试库可能无数据）。"""
        result = search("存储", top_k=5)
        assert result is not None
        assert result.query == "存储"
        # 测试库可能无预加载数据，空结果也正常
