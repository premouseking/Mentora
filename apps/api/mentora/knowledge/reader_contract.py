"""
LightRead-like 阅读器资源契约。

约定：
- resource_id 与 source_version_id 一一对应（兼容期）
- bbox 使用 PDF pt、左下角原点，与 ParsedBundle / EvidenceUnit 一致
- 正文版式由原始 PDF + pdf.js 渲染；blocks 仅用于 overlay / 目录 / 定位

@module mentora/knowledge/reader_contract
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceMeta(BaseModel):
    filename: str = ""
    media_type: str = ""
    byte_size: int = 0
    source_id: str = ""
    parser_name: str = ""
    parser_version: str = ""


class ResourceItem(BaseModel):
    resource_id: str = Field(description="资料版本 ID，等同 source_version_id")
    resource_name: str = ""
    resource_type: str = Field(default="pdf", description="pdf/docx/image/...")
    open_method: str = Field(default="pdf", description="pdf | markdown | image")
    pages: int = 0
    file_size: int = 0
    processing_status: str = ""
    updated_at: str | None = None
    meta: ResourceMeta = Field(default_factory=ResourceMeta)


class PdfPageInfo(BaseModel):
    page: int = Field(ge=1)
    width: float | None = None
    height: float | None = None
    thumbnail_url: str | None = None


class PdfBlock(BaseModel):
    idx: str = Field(description="块唯一标识，通常为 flat element index 或 evidence id")
    type: str = Field(description="heading/paragraph/table/image/list_item/formula")
    page: int = Field(ge=1)
    bbox: list[float] | None = Field(default=None, description="[x0,y0,x1,y1] PDF pt")
    text: str = ""
    level: int | None = None
    evidence_unit_id: str | None = None
    children: list[str] = Field(default_factory=list, description="子块 idx 列表")


class ReaderOutlineItem(BaseModel):
    id: str
    title: str
    page: int = Field(ge=1)
    level: int = Field(default=1, ge=1, le=6)
    block_idx: str | None = None
    children: list[ReaderOutlineItem] = Field(default_factory=list)


class PdfReaderDocument(BaseModel):
    resource: ResourceItem
    pdf_url: str
    pages: list[PdfPageInfo] = Field(default_factory=list)
    blocks: list[PdfBlock] = Field(default_factory=list)
    outline: list[ReaderOutlineItem] = Field(default_factory=list)
    parsed_bundle_ref: str = ""
    layout_ref: str = ""
    source_version_id: str = ""
