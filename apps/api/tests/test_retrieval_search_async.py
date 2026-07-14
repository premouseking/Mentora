import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from mentora.retrieval import search as search_module


def _unit(content: str, page_number: int = 1):
    return SimpleNamespace(
        id=uuid4(),
        bundle_id=uuid4(),
        source_version_id="source-v1",
        content=content,
        page_number=page_number,
    )


@pytest.mark.asyncio
async def test_retrieval_exposes_only_async_search_entrypoint():
    assert not hasattr(search_module, "search")
    assert not hasattr(search_module, "load_corpus")
    assert not hasattr(search_module, "_corpus")


@pytest.mark.asyncio
async def test_async_search_materializes_orm_evidence_from_recall_ids(monkeypatch):
    first = _unit("Photosynthesis converts light energy into chemical energy.", 1)
    second = _unit("Cell respiration releases stored chemical energy.", 2)

    async def fake_fts(**kwargs):
        return {str(first.id): 2.0, str(second.id): 1.0}

    async def fake_trgm(**kwargs):
        return {str(first.id): 0.9}

    async def fake_vector(**kwargs):
        return {}

    async def fake_fetch(evidence_ids):
        assert evidence_ids == [str(first.id), str(second.id)]
        return [first, second]

    async def fake_semantic_blocks(results):
        return results

    monkeypatch.setattr(search_module, "_recall_fts", fake_fts)
    monkeypatch.setattr(search_module, "_recall_trgm", fake_trgm)
    monkeypatch.setattr(search_module, "_recall_vector", fake_vector)
    monkeypatch.setattr(search_module, "_fetch_evidence_by_ids", fake_fetch)
    monkeypatch.setattr(search_module, "_apply_semantic_blocks_async", fake_semantic_blocks)

    result = await search_module.async_search("photosynthesis energy", top_k=2)

    assert [r.evidence.id for r in result.results] == [first.id, second.id]
    assert result.results[0].fts_score == 2.0
    assert result.results[0].trgm_score == 0.9


@pytest.mark.asyncio
async def test_async_search_runs_recall_layers_concurrently(monkeypatch):
    calls = []
    release = asyncio.Event()

    async def fake_fts(**kwargs):
        calls.append("fts-start")
        await release.wait()
        calls.append("fts-end")
        return {"same-doc": 2.0}

    async def fake_trgm(**kwargs):
        calls.append("trgm-start")
        release.set()
        calls.append("trgm-end")
        return {"same-doc": 1.0}

    async def fake_vector(**kwargs):
        return {}

    monkeypatch.setattr(search_module, "_recall_fts", fake_fts)
    monkeypatch.setattr(search_module, "_recall_trgm", fake_trgm)
    monkeypatch.setattr(search_module, "_recall_vector", fake_vector)
    monkeypatch.setattr(
        search_module,
        "_materialize_results",
        lambda *args, **kwargs: asyncio.sleep(0, result=[]),
    )

    result = await search_module.async_search("same", top_k=3)

    assert result.total_candidates == 1
    assert calls.index("trgm-start") < calls.index("fts-end")
