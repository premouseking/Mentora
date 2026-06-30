"""
检索数据模型：「单一证据事实 + 多种派生投影」。

约定：
- EvidenceUnit 是检索的事实源，保存稳定内容、页码、坐标和来源版本
- ChunkProjection 聚合 EvidenceUnit，承担默认 RAG 检索
- PageTextProjection 服务整页文本定位
- SentenceProjection 服务精确引用和局部查找
- source_version_id 当前为 CharField，等 WH 交付 Source/SourceVersion 后迁移为 FK

约束：
- 只对 ChunkProjection 全量生成向量（Embedding）
- SentenceProjection 保存位置但不全量生成向量
- 展示用引用标记不额外生成向量
- 所有模型通过 created_at 追踪时间线

@see docs/architecture/technical-solution.md §6
@see docs/architecture/module-boundaries.md
@module mentora/retrieval/models
"""

import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from pgvector.django import IvfflatIndex, VectorField


class EvidenceUnit(models.Model):
    """
    可引用的证据单元，检索的事实源。

    每个 EvidenceUnit 对应 ParsedBundle 中的一个或多个 ParsedElement，
    通过 element_indices 引用。内容可包含段落文本、标题等。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_version_id = models.CharField(
        max_length=128,
        db_index=True,
        help_text="关联的不可变资料版本 ID。等 WH 交付 SourceVersion 后迁移为 ForeignKey。",
    )
    bundle_id = models.UUIDField(
        db_index=True,
        help_text="所属 ParsedBundle ID，用于追溯解析产物。",
    )
    content = models.TextField(help_text="证据正文片段。")
    segmented_content = models.TextField(
        default="",
        help_text="jieba 分词后的文本（空格分隔），用于 PG tsvector 索引。",
    )
    search_vector = SearchVectorField(
        null=True,
        help_text="PG 全文检索向量，由应用层在写入时通过 jieba 分词 + to_tsvector 生成。",
    )
    page_number = models.IntegerField(help_text="所在页码，从 1 开始。")
    bbox_json = models.JSONField(
        null=True,
        blank=True,
        help_text="BoundingBox 序列化：{x0, y0, x1, y1}，PDF pt 单位，原点左下角。",
    )
    element_indices = models.JSONField(
        default=list,
        help_text="引用的 ParsedElement 序号（0-based，拍平后索引）。",
    )
    structure_type = models.CharField(
        max_length=32,
        default="paragraph",
        help_text="结构类型：paragraph, heading, table, formula, list_item。",
    )
    token_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Token 估算值，供上下文预算使用。",
    )
    artifact_ref = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="对象存储引用，图片类型指向 MinIO 中的图片文件。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_evidence_unit"
        verbose_name = "证据单元"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["source_version_id", "page_number"]),
            GinIndex(
                name="evidence_content_trgm_idx",
                fields=["content"],
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                name="evidence_search_vector_idx",
                fields=["search_vector"],
            ),
        ]

    def __str__(self) -> str:
        preview = self.content[:80].replace("\n", " ")
        return f"EvidenceUnit({self.id}) [{self.page_number}] {preview}"


class ChunkProjection(models.Model):
    """
    RAG 检索投影，聚合相邻 EvidenceUnit 为适合模型上下文的文本块。

    约定：
    - 这是唯一全量生成向量的投影
    - 每个 Chunk 包含若干相邻 EvidenceUnit 的内容拼接
    - 向量维度由 Embedding Provider 决定（默认 1536，OpenAI text-embedding-3-small）

    约束：
    - chunks 按 page_number 和 element_indices 排序
    - 相邻证据在同一个 Chunk 中共享上下文窗口
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_version_id = models.CharField(max_length=128, db_index=True)
    evidence_ids = models.JSONField(
        default=list,
        help_text="聚合的 EvidenceUnit ID 列表（保持顺序）。",
    )
    content = models.TextField(help_text="拼接后的完整文本块。")
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
        help_text="文本块向量，全量生成。",
    )
    token_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Token 估算值。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_chunk_projection"
        verbose_name = "块投影"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["source_version_id"]),
            IvfflatIndex(
                name="chunk_embedding_ivfflat_idx",
                fields=["embedding"],
                lists=100,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        preview = self.content[:80].replace("\n", " ")
        return f"Chunk({self.id}) {preview}"


class PageTextProjection(models.Model):
    """
    页面文本投影，服务整页文本定位和关键词检索。

    约定：
    - 每个 SourceVersion 的每一页生成一条投影
    - 文本保留原始顺序（不重组阅读顺序）
    - 不生成向量（展示定位用，非语义检索）

    约束：
    - 仅对文本 PDF 生成；图片页不生成此投影
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_version_id = models.CharField(max_length=128, db_index=True)
    page_number = models.IntegerField()
    full_text = models.TextField(help_text="该页全部文本内容。")
    search_vector = SearchVectorField(
        null=True,
        help_text="PG 全文检索向量，在 save() 时由 full_text 自动同步。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_page_text_projection"
        verbose_name = "页面文本投影"
        verbose_name_plural = verbose_name
        unique_together = [("source_version_id", "page_number")]
        indexes = [
            GinIndex(
                name="page_text_search_idx",
                fields=["search_vector"],
            ),
        ]

    def __str__(self) -> str:
        return f"PageText({self.source_version_id}) p{self.page_number}"

    def save(self, *args, **kwargs) -> None:
        """保存后同步填充 search_vector，供 PG 全文检索使用。"""
        super().save(*args, **kwargs)
        type(self).objects.filter(pk=self.pk).update(
            search_vector=SearchVector("full_text", config="simple"),
        )
        self.refresh_from_db(fields=["search_vector"])


class SentenceProjection(models.Model):
    """
    句子级投影，服务精确引用和局部查找。

    约定：
    - 句子位置全量保存
    - 句子向量按需求生成（不默认全量）
    - 用于回答中的精确原文定位

    约束：
    - evidence_unit_id 引用所属 EvidenceUnit
    - position_index 为句子在原文中的序号
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence_unit_id = models.UUIDField(db_index=True)
    position_index = models.IntegerField(help_text="句子在所属 EvidenceUnit 中的序号（0-based）。")
    content = models.TextField(help_text="单个句子的文本。")
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
        help_text="句子向量，按需求生成（不默认全量）。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_sentence_projection"
        verbose_name = "句子投影"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["evidence_unit_id"]),
            IvfflatIndex(
                name="sentence_embedding_ivfflat_idx",
                fields=["embedding"],
                lists=50,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        preview = self.content[:60]
        return f"Sentence({self.evidence_unit_id})[{self.position_index}] {preview}"


class EvidenceSnapshot(models.Model):
    """
    不可变证据快照，冻结一次模型调用引用的 EvidenceUnit 集合。

    约定：
    - 在每次 agent_runtime 模型调用前创建，记录当时引用的 evidence ID 列表
    - 历史回答通过 snapshot_id → get_evidence_by_ids() 回溯到当时的原文
    - 资料重解析后旧 EvidenceUnit 可能被替换，snapshot 确保引用可追溯

    参考：LightRead TaskSnapshotModel 的不可变快照模式
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence_ids = models.JSONField(
        default=list,
        help_text="冻结的证据 ID 列表（有序）。",
    )
    scope_revision_id = models.CharField(
        max_length=128,
        db_index=True,
        help_text="课程知识作用域修订 ID，关联 CourseProfileRevision。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_evidence_snapshot"
        verbose_name = "证据快照"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["scope_revision_id", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"EvidenceSnapshot({self.id}) [{len(self.evidence_ids)} ids]"


class BenchmarkResult(models.Model):
    """
    检索基准运行结果持久化，用于追踪回归。

    约定：
    - 每次 benchmark run() 完成后写入一条记录
    - summary 存汇总指标，details 存逐查询明细
    - 按 name 分组可对比不同 benchmark 类型的历史趋势
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Benchmark 名称：runner / vector / compare",
    )
    corpus_size = models.IntegerField()
    summary = models.JSONField(help_text="汇总指标：avg_p_at_5, avg_p_at_10, avg_recall 等")
    details = models.JSONField(help_text="逐查询明细列表")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "retrieval_benchmark_result"
        verbose_name = "基准结果"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"Benchmark({self.name}) P@5={self.summary.get('avg_p_at_5', '-')} "
            f"P@10={self.summary.get('avg_p_at_10', '-')}"
        )
