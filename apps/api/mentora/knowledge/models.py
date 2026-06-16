"""
用户资源库数据模型：资料身份、不可变版本、上传会话与处理运行。

约定：
- SourceVersion 一旦创建不可修改内容字段，仅 processing_status 等运行态可更新
- object_key / artifact_ref 仅存对象存储逻辑键，不存本地绝对路径
- owner_id 当前为字符串占位，待认证模块交付后迁移为用户 FK

约束：
- 上传完成前不得创建 SourceVersion
- ProcessingRun 通过 idempotency_key 保证同一内容+解析器版本不重复处理

@see docs/architecture/scope-versioning-design.md §4.1
@module mentora/knowledge/models
"""

import uuid

from django.db import models


class SourceStatus(models.TextChoices):
    ACTIVE = "active", "可用"
    ARCHIVED = "archived", "已归档"


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", "待处理"
    PROCESSING = "processing", "处理中"
    COMPLETED = "completed", "已完成"
    FAILED = "failed", "失败"


class UploadSessionStatus(models.TextChoices):
    PENDING = "pending", "待上传"
    UPLOADING = "uploading", "上传中"
    COMPLETED = "completed", "已完成"
    FAILED = "failed", "失败"


class ProcessingRunStatus(models.TextChoices):
    PENDING = "pending", "待执行"
    RUNNING = "running", "执行中"
    COMPLETED = "completed", "已完成"
    FAILED = "failed", "失败"
    CANCELLED = "cancelled", "已取消"


class Source(models.Model):
    """用户资源库中的逻辑资料。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.CharField(max_length=64, db_index=True, help_text="资料所有者 ID")
    display_title = models.CharField(max_length=512, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=SourceStatus.choices,
        default=SourceStatus.ACTIVE,
    )
    latest_version = models.ForeignKey(
        "SourceVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="最新资料版本",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_source"
        verbose_name = "资料"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["owner_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Source({self.id}) {self.display_title or '未命名'}"


class SourceVersion(models.Model):
    """不可变资料版本，绑定对象存储中的原始文件。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_versions",
    )
    content_sha256 = models.CharField(max_length=64, db_index=True)
    object_key = models.CharField(max_length=512, help_text="原始文件对象存储键")
    media_type = models.CharField(max_length=128, default="application/pdf")
    byte_size = models.BigIntegerField()
    original_filename = models.CharField(max_length=512, blank=True, default="")
    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    artifact_ref = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="ParsedBundle JSON 对象存储键",
    )
    parser_name = models.CharField(max_length=64, blank=True, default="")
    parser_version = models.CharField(max_length=32, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_source_version"
        verbose_name = "资料版本"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["source", "version_number"],
                name="knowledge_srcver_version_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["content_sha256"]),
            models.Index(fields=["processing_status"]),
        ]

    def __str__(self) -> str:
        return f"SourceVersion({self.id}) v{self.version_number}"


class UploadSession(models.Model):
    """上传会话，关联预签名 PUT 与后续 complete 校验。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.CharField(max_length=64, db_index=True)
    object_key = models.CharField(max_length=512)
    status = models.CharField(
        max_length=16,
        choices=UploadSessionStatus.choices,
        default=UploadSessionStatus.PENDING,
    )
    expected_byte_size = models.BigIntegerField(null=True, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True, default="")
    media_type = models.CharField(max_length=128, default="application/pdf")
    original_filename = models.CharField(max_length=512, blank=True, default="")
    source_version = models.ForeignKey(
        SourceVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="upload_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_upload_session"
        verbose_name = "上传会话"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return f"UploadSession({self.id}) {self.status}"


class ProcessingRun(models.Model):
    """解析/入库处理运行记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_version = models.ForeignKey(
        SourceVersion,
        on_delete=models.CASCADE,
        related_name="processing_runs",
    )
    status = models.CharField(
        max_length=16,
        choices=ProcessingRunStatus.choices,
        default=ProcessingRunStatus.PENDING,
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    parser_name = models.CharField(max_length=64, default="pymupdf")
    parser_version = models.CharField(max_length=32, default="1.23.0")
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_processing_run"
        verbose_name = "处理运行"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["source_version", "status"]),
        ]

    def __str__(self) -> str:
        return f"ProcessingRun({self.id}) {self.status}"
