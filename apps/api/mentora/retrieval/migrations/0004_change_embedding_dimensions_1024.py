"""
向量维度迁移：1536 → 1024。

原因：切换到豆包 Embedding（Doubao-1.5-Embedding），
MRL 降维 1024d 平衡性能与存储。

前提：当前表中无实际 embedding 数据（全为 NULL），
     ALTER COLUMN 不会丢失数据。
"""

import pgvector.django.vector
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retrieval", "0003_add_segmented_search_vector"),
    ]

    operations = [
        # 1. 移除 ChunkProjection 上的 IVFFlat 索引（改维度前必须先删索引）
        migrations.RemoveIndex(
            model_name="chunkprojection",
            name="chunk_embedding_ivfflat_idx",
        ),
        # 2. 改 ChunkProjection.embedding 维度
        migrations.AlterField(
            model_name="chunkprojection",
            name="embedding",
            field=pgvector.django.vector.VectorField(
                blank=True,
                dimensions=1024,
                help_text="文本块向量，全量生成。豆包 Embedding MRL 1024d。",
                null=True,
            ),
        ),
        # 3. 改 SentenceProjection.embedding 维度
        migrations.AlterField(
            model_name="sentenceprojection",
            name="embedding",
            field=pgvector.django.vector.VectorField(
                blank=True,
                dimensions=1024,
                help_text="句子向量，按需求生成（不默认全量）。",
                null=True,
            ),
        ),
        # 4. 重建 IVFFlat 索引（lists 不变）
        migrations.AddIndex(
            model_name="chunkprojection",
            index=pgvector.django.IvfflatIndex(
                fields=["embedding"],
                lists=100,
                name="chunk_embedding_ivfflat_idx",
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
