"""Embedding Provider 测试。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mentora.retrieval.embedding_provider import DoubaoEmbeddingProvider


def _fake_response(texts: list[str], dimensions: int = 1024):
    """构造模拟的豆包 API 响应。"""
    return json.dumps({
        "data": [
            {
                "index": i,
                "embedding": [0.1 * (i + 1)] * dimensions,
            }
            for i in range(len(texts))
        ],
    }).encode("utf-8")


class TestDoubaoProvider:
    """DoubaoEmbeddingProvider 单元测试（mock HTTP）。"""

    @pytest.fixture
    def provider(self):
        return DoubaoEmbeddingProvider(
            api_key="test-key",
            model="doubao-embedding",
            dimensions=1024,
        )

    def test_dimensions_property(self, provider):
        assert provider.dimensions == 1024

    def test_empty_texts(self, provider):
        """空列表直接返回空。"""
        assert provider.embed([]) == []

    def test_single_text(self, provider):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                _fake_response(["测试文本"])
            )
            result = provider.embed(["测试文本"])
            assert len(result) == 1
            assert len(result[0]) == 1024

    def test_batch_split(self, provider):
        """超过 batch_size 时分批请求。"""
        provider._batch_size = 2
        texts = ["a", "b", "c", "d"]
        call_count = [0]

        def side_effect(req, timeout):
            call_count[0] += 1
            body = json.loads(req.data.decode("utf-8"))
            mock = MagicMock()
            mock.read.return_value = _fake_response(body["input"])
            mock.__enter__.return_value = mock
            return mock

        with patch("urllib.request.urlopen", side_effect=side_effect):
            result = provider.embed(texts)

        assert len(result) == 4
        assert call_count[0] == 2  # 4 条 / batch_size=2 → 2 次请求

    def test_returns_in_order(self, provider):
        """结果顺序与输入一致。"""
        texts = ["第一段", "第二段", "第三段"]
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                _fake_response(texts)
            )
            result = provider.embed(texts)
        # 每段的第一维不同（0.1, 0.2, 0.3），可区分
        assert result[0][0] == pytest.approx(0.1)
        assert result[1][0] == pytest.approx(0.2)
        assert result[2][0] == pytest.approx(0.3)

    def test_dimension_mismatch_raises(self, provider):
        """返回维度与预期不符时抛异常。"""
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                _fake_response(["文本"], dimensions=2048)
            )
            with pytest.raises(RuntimeError):
                provider.embed(["文本"])

    def test_count_mismatch_raises(self, provider):
        """返回向量数与输入数不一致时抛异常。"""
        with patch("urllib.request.urlopen") as mock_open:
            # 返回 1 条但输入了 2 条
            mock_open.return_value.__enter__.return_value.read.return_value = (
                _fake_response(["仅一条"])
            )
            with pytest.raises(RuntimeError):
                provider.embed(["第一段", "第二段"])

    def test_retry_on_error(self, provider):
        """网络错误时重试。"""
        provider._max_retries = 3
        call_count = [0]

        def side_effect(req, timeout):
            call_count[0] += 1
            if call_count[0] < 3:
                raise OSError("网络不可达")
            mock = MagicMock()
            mock.read.return_value = _fake_response(["成功"])
            mock.__enter__.return_value = mock
            return mock

        with patch("urllib.request.urlopen", side_effect=side_effect):
            result = provider.embed(["成功"])

        assert len(result) == 1
        assert call_count[0] == 3  # 前 2 次失败，第 3 次成功

    def test_all_retries_exhausted(self, provider):
        """所有重试均失败时抛 RuntimeError。"""
        provider._max_retries = 2

        with patch("urllib.request.urlopen", side_effect=OSError("网络不可达")):
            with pytest.raises(RuntimeError):
                provider.embed(["失败"])
