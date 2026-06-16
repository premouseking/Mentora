"""
检索模块 Celery 任务。

约定：
- Embedding 生成任务幂等：已有 embedding 的 Chunk 跳过
- 批量写入减少 DB 往返
- 任务可重试（网络/API 临时不可用）

约束：
- 依赖 VOLCANO_ENGINE_API_KEY 环境变量
- 首次运行前需先完成 evidence 入库和 Chunk 构建

@module mentora.retrieval.tasks
"""

from celery import shared_task

from mentora.retrieval.embedding_provider import get_provider
from mentora.retrieval.models import ChunkProjection


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(IOError, OSError, RuntimeError),
)
def generate_chunk_embeddings(
    self,
    source_version_id: str | None = None,
    batch_size: int = 100,
) -> dict:
    """
    为指定 source_version 下未生成 embedding 的 Chunk 批量生成向量。

    参数：
        source_version_id: 资料版本 ID，None 表示处理全部
        batch_size: 每批调用 embedding API 的文本数

    返回：
        {"processed": int, "skipped": int, "errors": int}
    """
    qs = ChunkProjection.objects.filter(embedding__isnull=True)
    if source_version_id is not None:
        qs = qs.filter(source_version_id=source_version_id)

    chunk_ids = list(qs.values_list("id", flat=True))
    if not chunk_ids:
        return {"processed": 0, "skipped": 0, "errors": 0}

    provider = get_provider()
    processed = 0
    errors = 0

    for i in range(0, len(chunk_ids), batch_size):
        batch_ids = chunk_ids[i:i + batch_size]
        # 重新查询确保拿到最新数据（避免 stale queryset）
        batch = list(
            ChunkProjection.objects.filter(id__in=batch_ids)
            .only("id", "content")
        )
        if not batch:
            continue

        texts = [c.content for c in batch]
        try:
            embeddings = provider.embed(texts)
        except Exception:
            errors += len(batch)
            continue

        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding
        ChunkProjection.objects.bulk_update(batch, ["embedding"])
        processed += len(batch)

    skipped = ChunkProjection.objects.filter(
        embedding__isnull=False,
    ).count()
    if source_version_id is not None:
        skipped = ChunkProjection.objects.filter(
            source_version_id=source_version_id,
            embedding__isnull=False,
        ).count()

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }
