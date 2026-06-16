"""检索 API 端点测试。"""

import json

import pytest
from django.test import RequestFactory

from mentora.retrieval.views import locate_view, search_view


@pytest.fixture
def rf():
    return RequestFactory()


class TestSearchView:
    """GET /api/retrieval/search 测试。"""

    def test_search_returns_results(self, rf):
        """正常查询应返回匹配结果。"""
        request = rf.get("/api/retrieval/search", {"q": "直接映射", "top_k": 3})
        response = search_view(request)
        assert response.status_code == 200

        data = json.loads(response.content)
        assert data["query"] == "直接映射"
        assert "results" in data
        assert data["total_candidates"] > 0
        assert "elapsed_ms" in data

    def test_search_empty_query(self, rf):
        """空查询返回 400。"""
        request = rf.get("/api/retrieval/search", {"q": ""})
        response = search_view(request)
        assert response.status_code == 400

    def test_search_missing_query(self, rf):
        """缺少 q 参数返回 400。"""
        request = rf.get("/api/retrieval/search")
        response = search_view(request)
        assert response.status_code == 400

    def test_search_top_k_respected(self, rf):
        """top_k 参数应限制结果数量。"""
        request = rf.get("/api/retrieval/search", {"q": "Cache", "top_k": 1})
        response = search_view(request)
        data = json.loads(response.content)
        assert len(data["results"]) <= 1

    def test_search_results_include_scores(self, rf):
        """每条结果应包含评分信息。"""
        request = rf.get("/api/retrieval/search", {"q": "Cache 映射"})
        response = search_view(request)
        data = json.loads(response.content)
        for r in data["results"]:
            assert "score" in r
            assert "fts_score" in r
            assert "trgm_score" in r
            assert "evidence_id" in r
            assert "page_number" in r
            assert "content_preview" in r

    def test_search_fuzzy_typo(self, rf):
        """用户输入错别字（cache的对应方式）应能通过 trgm 路模糊匹配。"""
        request = rf.get("/api/retrieval/search", {"q": "cache的对应方式"})
        response = search_view(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        # trgm 层应对错别字有一定容错
        assert data["total_candidates"] > 0


class TestLocateView:
    """GET /api/retrieval/evidence/<uuid>/location 测试。"""

    def test_locate_valid_evidence(self, rf):
        """有效 Evidence ID 返回完整定位。"""
        # 使用金标集中的已知 ID
        evidence_id = "e8d1a2b3-0001-4000-8000-000000000001"
        response = locate_view(request=rf.get("/"), evidence_id=evidence_id)
        assert response.status_code == 200

        data = json.loads(response.content)
        assert data["evidence_id"] == evidence_id
        assert data["page_number"] > 0
        assert len(data["content"]) > 0

    def test_locate_nonexistent_evidence(self, rf):
        """不存在的 Evidence ID 返回 404。"""
        response = locate_view(
            request=rf.get("/"),
            evidence_id="e8d1a2b3-9999-4000-8000-000000000999",
        )
        assert response.status_code == 404

    def test_locate_includes_context(self, rf):
        """定位结果应包含上下文窗口。"""
        evidence_id = "e8d1a2b3-0001-4000-8000-000000000002"
        response = locate_view(request=rf.get("/"), evidence_id=evidence_id)
        data = json.loads(response.content)
        assert "context_before" in data
        assert "context_after" in data
