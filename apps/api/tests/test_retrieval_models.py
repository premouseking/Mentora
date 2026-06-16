"""检索模型行为测试。"""

import pytest

from mentora.retrieval.models import PageTextProjection


@pytest.mark.django_db
def test_page_text_projection_populates_search_vector():
    """PageTextProjection 保存后应自动填充 search_vector。"""
    page = PageTextProjection.objects.create(
        source_version_id="sv-test-1",
        page_number=1,
        full_text="直接映射 Cache 行",
    )
    assert page.search_vector is not None
