"""
知识主题数据模型：主题节点、前置关系、主题-证据关联。

约定：
- Topic 树通过 parent FK 自引用，level 表示层级深度
- TopicEdge 表达前置依赖（前后关系）
- TopicEvidence 关联 retrieval.EvidenceUnit（通过 evidence_unit_id 字符串引用）

@module mentora/topics/models
"""

import uuid

from django.db import models


class Topic(models.Model):
    """知识主题节点——课程的知识图谱中的节点。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="topics",
        help_text="正式课程 FK",
    )
    legacy_course_key = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        default="",
        help_text="legacy 关联键（deprecated，见 ADR-0008）",
    )
    name = models.CharField(max_length=256, help_text="主题名称")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE,
        related_name="children",
        help_text="父主题，根节点为 None",
    )
    level = models.IntegerField(default=0, help_text="层级: 0=根, 1=章, 2=节")
    position = models.IntegerField(default=0, help_text="排序序号")
    evidence_count = models.IntegerField(default=0, help_text="关联证据数")
    estimated_minutes = models.IntegerField(default=0, help_text="预估学习时长（分钟）")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "topics_topic"
        verbose_name = "知识主题"
        verbose_name_plural = verbose_name
        ordering = ["course", "level", "position"]
        indexes = [
            models.Index(fields=["course"]),
            models.Index(fields=["course", "parent"]),
            models.Index(fields=["legacy_course_key"]),
        ]

    def __str__(self) -> str:
        return f"Topic({self.id}) [{self.level}] {self.name}"


class TopicEdge(models.Model):
    """主题间前置关系。"""

    class Relation(models.TextChoices):
        REQUIRES = "requires", "必须先学"
        SUGGESTS = "suggests", "建议先学"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="outgoing_edges",
        help_text="后置主题",
    )
    target = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="incoming_edges",
        help_text="前置主题",
    )
    relation = models.CharField(max_length=16, choices=Relation.choices, default=Relation.REQUIRES)

    class Meta:
        db_table = "topics_edge"
        verbose_name = "主题前置关系"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target"],
                name="topics_edge_source_target_unique",
            ),
        ]


class TopicEvidence(models.Model):
    """主题与检索证据的关联。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="evidence_links",
    )
    evidence_unit_id = models.CharField(
        max_length=128, db_index=True,
        help_text="关联的 EvidenceUnit ID（字符串引用，跨模块）",
    )
    relevance = models.FloatField(default=1.0, help_text="关联度 0-1")

    class Meta:
        db_table = "topics_evidence"
        verbose_name = "主题证据关联"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "evidence_unit_id"],
                name="topics_evidence_topic_eid_unique",
            ),
        ]
