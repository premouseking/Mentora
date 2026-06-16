"""Embedding 生成 Celery 任务测试。"""

import uuid

import pytest

from mentora.retrieval.models import ChunkProjection


@pytest.fixture
def provider_mock():
    """注入模拟 Embedding Provider 到任务使用的 get_provider。"""
    from unittest.mock import MagicMock, patch

    mock = MagicMock()
    mock.dimensions = 1024

    def _fake_embed(texts):
        return [[0.01 * (idx + 1)] * 1024 for idx in range(len(texts))]

    mock.embed.side_effect = _fake_embed
    return mock


@pytest.mark.django_db(transaction=True)
class TestGenerateChunkEmbeddings:
    """generate_chunk_embeddings 任务测试。"""

    def test_empty_no_chunks(self, provider_mock):
        """无 Chunk 时返回 processed=0。"""
        from unittest.mock import patch

        from mentora.retrieval.tasks import generate_chunk_embeddings

        with patch(
            "mentora.retrieval.tasks.get_provider",
            return_value=provider_mock,
        ):
            result = generate_chunk_embeddings(source_version_id="sv-nonexist")
        assert result["processed"] == 0
        assert result["errors"] == 0

    def test_generates_embeddings(self, provider_mock):
        """为无 embedding 的 Chunk 生成向量。"""
        from unittest.mock import patch

        from mentora.retrieval.tasks import generate_chunk_embeddings

        sv = "sv-embed-test"
        # 创建 3 个无 embedding 的 Chunk
        ids = [uuid.uuid4() for _ in range(3)]
        for i, cid in enumerate(ids):
            ChunkProjection.objects.create(
                id=cid,
                source_version_id=sv,
                evidence_ids=[str(uuid.uuid4())],
                content=f"测试内容段落 {i + 1}。",
                embedding=None,
            )

        with patch(
            "mentora.retrieval.tasks.get_provider",
            return_value=provider_mock,
        ):
            result = generate_chunk_embeddings(source_version_id=sv)

        assert result["processed"] == 3
        assert result["errors"] == 0

        # 验证实际写入
        for cid in ids:
            chunk = ChunkProjection.objects.get(id=cid)
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1024

    def test_skips_existing_embeddings(self, provider_mock):
        """已有 embedding 的 Chunk 跳过。"""
        from unittest.mock import patch

        from mentora.retrieval.tasks import generate_chunk_embeddings

        sv = "sv-skip-test"
        # 一个有 embedding，一个没有
        ChunkProjection.objects.create(
            id=uuid.uuid4(),
            source_version_id=sv,
            evidence_ids=[str(uuid.uuid4())],
            content="已有 embedding。",
            embedding=[0.1] * 1024,
        )
        new_id = uuid.uuid4()
        ChunkProjection.objects.create(
            id=new_id,
            source_version_id=sv,
            evidence_ids=[str(uuid.uuid4())],
            content="无 embedding。",
            embedding=None,
        )

        with patch(
            "mentora.retrieval.tasks.get_provider",
            return_value=provider_mock,
        ):
            result = generate_chunk_embeddings(source_version_id=sv)

        # 仅处理了 1 个
        assert result["processed"] == 1

    def test_handles_provider_error(self, provider_mock):
        """Provider 异常时记录 errors 但不中断。"""
        from unittest.mock import patch

        from mentora.retrieval.tasks import generate_chunk_embeddings

        sv = "sv-error-test"
        ChunkProjection.objects.create(
            id=uuid.uuid4(),
            source_version_id=sv,
            evidence_ids=[str(uuid.uuid4())],
            content="会导致错误。",
            embedding=None,
        )

        provider_mock.embed.side_effect = RuntimeError("API 不可用")

        with patch(
            "mentora.retrieval.tasks.get_provider",
            return_value=provider_mock,
        ):
            result = generate_chunk_embeddings(source_version_id=sv)

        assert result["errors"] >= 1
        assert result["processed"] == 0

    def test_all_source_versions_when_none(self, provider_mock):
        """source_version_id=None 时处理所有版本。"""
        from unittest.mock import patch

        from mentora.retrieval.tasks import generate_chunk_embeddings

        for sv in ["sv-a", "sv-b"]:
            ChunkProjection.objects.create(
                id=uuid.uuid4(),
                source_version_id=sv,
                evidence_ids=[str(uuid.uuid4())],
                content=f"{sv} 的内容。",
                embedding=None,
            )

        with patch(
            "mentora.retrieval.tasks.get_provider",
            return_value=provider_mock,
        ):
            result = generate_chunk_embeddings(source_version_id=None)

        assert result["processed"] == 2
        assert result["errors"] == 0
