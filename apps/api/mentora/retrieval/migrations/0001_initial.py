"""
检索模块初始迁移。

创建 EvidenceUnit、ChunkProjection、PageTextProjection、SentenceProjection 四个模型。

依赖：pgvector 扩展已启用（CREATE EXTENSION IF NOT EXISTS vector）
       pg_trgm 扩展已启用（CREATE EXTENSION IF NOT EXISTS pg_trgm）
"""

import uuid

import pgvector.django.vector
from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations, models
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # 无跨 app 依赖；source_version_id 当前为 CharField，
        # 等 WH 交付 SourceVersion 模型后追加 FK migration
    ]

    operations = [
        VectorExtension(),
        TrigramExtension(),
        # ── EvidenceUnit ──────────────────────────────
        migrations.CreateModel(
            name="EvidenceUnit",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source_version_id",
                    models.CharField(
                        db_index=True,
                        help_text="关联的不可变资料版本 ID。等 WH 交付 SourceVersion 后迁移为 ForeignKey。",
                        max_length=128,
                    ),
                ),
                (
                    "bundle_id",
                    models.UUIDField(
                        db_index=True,
                        help_text="所属 ParsedBundle ID，用于追溯解析产物。",
                    ),
                ),
                ("content", models.TextField(help_text="证据正文片段。")),
                (
                    "page_number",
                    models.IntegerField(help_text="所在页码，从 1 开始。"),
                ),
                (
                    "bbox_json",
                    models.JSONField(
                        blank=True,
                        help_text="BoundingBox 序列化：{x0, y0, x1, y1}，PDF pt 单位，原点左下角。",
                        null=True,
                    ),
                ),
                (
                    "element_indices",
                    models.JSONField(
                        default=list,
                        help_text="引用的 ParsedElement 序号（0-based，拍平后索引）。",
                    ),
                ),
                (
                    "structure_type",
                    models.CharField(
                        default="paragraph",
                        help_text="结构类型：paragraph, heading, table, formula, list_item。",
                        max_length=32,
                    ),
                ),
                (
                    "token_count",
                    models.IntegerField(
                        blank=True,
                        help_text="Token 估算值，供上下文预算使用。",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "retrieval_evidence_unit",
                "verbose_name": "证据单元",
                "verbose_name_plural": "证据单元",
            },
        ),
        migrations.AddIndex(
            model_name="EvidenceUnit",
            index=models.Index(
                fields=["source_version_id", "page_number"],
                name="evidence_srcver_page_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="EvidenceUnit",
            index=GinIndex(
                fields=["content"],
                name="evidence_content_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),

        # ── ChunkProjection ────────────────────────────
        migrations.CreateModel(
            name="ChunkProjection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source_version_id",
                    models.CharField(db_index=True, max_length=128),
                ),
                (
                    "evidence_ids",
                    models.JSONField(
                        default=list,
                        help_text="聚合的 EvidenceUnit ID 列表（保持顺序）。",
                    ),
                ),
                ("content", models.TextField(help_text="拼接后的完整文本块。")),
                (
                    "embedding",
                    pgvector.django.vector.VectorField(
                        blank=True,
                        dimensions=1536,
                        help_text="文本块向量，全量生成。",
                        null=True,
                    ),
                ),
                (
                    "token_count",
                    models.IntegerField(
                        blank=True,
                        help_text="Token 估算值。",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "retrieval_chunk_projection",
                "verbose_name": "块投影",
                "verbose_name_plural": "块投影",
            },
        ),
        migrations.AddIndex(
            model_name="ChunkProjection",
            index=models.Index(
                fields=["source_version_id"],
                name="chunk_srcver_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ChunkProjection",
            index=pgvector.django.IvfflatIndex(
                fields=["embedding"],
                lists=100,
                name="chunk_embedding_ivfflat_idx",
                opclasses=["vector_cosine_ops"],
            ),
        ),

        # ── PageTextProjection ─────────────────────────
        migrations.CreateModel(
            name="PageTextProjection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source_version_id",
                    models.CharField(db_index=True, max_length=128),
                ),
                ("page_number", models.IntegerField()),
                ("full_text", models.TextField(help_text="该页全部文本内容。")),
                (
                    "search_vector",
                    SearchVectorField(
                        help_text="PG 全文检索向量，由数据库触发器或应用层维护。",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "retrieval_page_text_projection",
                "verbose_name": "页面文本投影",
                "verbose_name_plural": "页面文本投影",
                "unique_together": {("source_version_id", "page_number")},
            },
        ),
        migrations.AddIndex(
            model_name="PageTextProjection",
            index=GinIndex(
                fields=["search_vector"],
                name="page_text_search_idx",
            ),
        ),

        # ── SentenceProjection ─────────────────────────
        migrations.CreateModel(
            name="SentenceProjection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "evidence_unit_id",
                    models.UUIDField(db_index=True),
                ),
                (
                    "position_index",
                    models.IntegerField(
                        help_text="句子在所属 EvidenceUnit 中的序号（0-based）。"
                    ),
                ),
                ("content", models.TextField(help_text="单个句子的文本。")),
                (
                    "embedding",
                    pgvector.django.vector.VectorField(
                        blank=True,
                        dimensions=1536,
                        help_text="句子向量，按需求生成（不默认全量）。",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "retrieval_sentence_projection",
                "verbose_name": "句子投影",
                "verbose_name_plural": "句子投影",
            },
        ),
        migrations.AddIndex(
            model_name="SentenceProjection",
            index=models.Index(
                fields=["evidence_unit_id"],
                name="sentence_evidence_idx",
            ),
        ),
    ]
