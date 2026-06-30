"""
解析产物和证据单元的数据契约。

约定：
- 页码 page_number 从 1 开始递增，映射到文档的物理页序
- original_label 保留原文件的页码标注（如 "iii"、"A-1"），不参与计算
- 坐标使用 PDF 标准坐标系：原点为左下角，单位为点（pt, 1/72 英寸）
- EvidenceUnit 通过 element_indices 引用 ParsedElement，不复制坐标

约束：
- BoundingBox 的 x1 >= x0, y1 >= y0
- page_number >= 1
- content_hash 使用 SHA-256 十六进制字符串
- 非法元素（负坐标、空文本元素等）在校验时拒绝

@see docs/architecture/adr/0006-parsed-bundle-evidence-schema.md
@module mentora/parsing/schemas
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ElementType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    FORMULA = "formula"
    IMAGE = "image"
    LIST_ITEM = "list_item"


class BoundingBox(BaseModel):
    """
    PDF 坐标矩形。

    约束：原点为左下角，单位为 pt；x1 >= x0，y1 >= y0。
    """

    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def _check_non_degenerate(self) -> "BoundingBox":
        if self.x1 < self.x0:
            raise ValueError(f"x1 ({self.x1}) must be >= x0 ({self.x0})")
        if self.y1 < self.y0:
            raise ValueError(f"y1 ({self.y1}) must be >= y0 ({self.y0})")
        return self


class ParsedElement(BaseModel):
    """
    单个解析元素（段落、标题、表格、公式、图片或列表项）。
    """

    type: ElementType
    text: str = Field(default="", description="元素的文本内容；图片可为空")
    bbox: BoundingBox | None = Field(default=None, description="PDF 坐标矩形，不可用时为 None")
    heading_level: int | None = Field(
        default=None, ge=1, le=6, description="当 type=heading 时的层级"
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="提取置信度，0-1"
    )
    extra: dict | None = Field(
        default=None, description="扩展数据，图片元素存储 {xref, width, height}"
    )


class Page(BaseModel):
    """
    解析后的单个页面，元素按阅读顺序排列。
    """

    page_number: int = Field(ge=1, description="物理页码，从 1 开始")
    original_label: str | None = Field(default=None, description="原文件页码标注")
    elements: list[ParsedElement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParserInfo(BaseModel):
    """解析器身份和版本信息，参与幂等键计算。"""

    name: str = Field(description="解析器名称，例如 'pymupdf'")
    version: str = Field(description="解析器版本号，例如 '1.23.0'")


class QualityInfo(BaseModel):
    """
    解析质量评估。

    约束：score 为 0-1，供后续 OCR 决策参考。
    """

    score: float | None = Field(default=None, ge=0.0, le=1.0)
    text_page_ratio: float | None = Field(
        default=None, ge=0.0, le=1.0, description="有效文本页比例"
    )
    garbled_ratio: float | None = Field(
        default=None, ge=0.0, le=1.0, description="乱码/替换字符比例"
    )


class ParsedBundle(BaseModel):
    """
    一次完整解析的产物。

    约定：
    - 同一个 ContentHash + ParserVersion 产生相同结果
    - artifact_ref 指向对象存储中的完整 JSON 产物
    - 数据库不存储 bundle 正文，只存储 ID 和引用
    """

    id: UUID = Field(default_factory=uuid4, description="稳定主键")
    source_version_id: str = Field(description="关联的不可变资料版本 ID")
    parser: ParserInfo
    content_hash: str = Field(
        min_length=64,
        max_length=64,
        description="原始文件 SHA-256 十六进制摘要",
    )
    pages: list[Page] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    quality: QualityInfo = Field(default_factory=QualityInfo)
    artifact_ref: str = Field(default="", description="对象存储键，持久化后回填")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def element_count(self) -> int:
        return sum(len(page.elements) for page in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class EvidenceUnit(BaseModel):
    """
    可引用的证据单元。

    约定：
    - 通过 element_indices 引用 ParsedBundle 中的 ParsedElement
    - id 为稳定 UUID，Tutor 的回答引用此 ID
    - 内容变更（重新解析）时旧 EvidenceUnit 失效，创建新 EvidenceUnit
    """

    id: UUID = Field(default_factory=uuid4, description="稳定引用 ID")
    bundle_id: UUID = Field(description="所属 ParsedBundle ID")
    source_version_id: str = Field(description="资料版本 ID，便于过滤")
    content: str = Field(min_length=1, description="证据正文片段")
    page_number: int = Field(ge=1, description="所在页码")
    bbox: BoundingBox | None = Field(default=None, description="证据在页面中的位置")
    element_indices: list[int] = Field(
        default_factory=list,
        description="引用的 ParsedElement 序号（0-based，在 ParsedBundle.pages 拍平后的索引）",
    )
    token_count: int | None = Field(default=None, ge=0, description="Token 估算值")
    structure_type: str = Field(
        default="paragraph",
        description="结构类型：paragraph/heading/table/formula/image/list_item",
    )
    artifact_ref: str = Field(
        default="",
        description="对象存储引用，图片类型存图片 URL",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceSnapshot(BaseModel):
    """
    单次模型调用使用的不可变证据集合。

    约束：
    - 在每个 LearningSession 或模型调用开始时快照
    - 历史回答始终可回溯到具体 EvidenceUnit ID 列表
    """

    id: UUID = Field(default_factory=uuid4)
    evidence_ids: list[UUID] = Field(default_factory=list)
    scope_revision_id: str = Field(description="课程知识作用域修订 ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
