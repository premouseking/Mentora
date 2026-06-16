"""
PyMuPDF 解析适配器。

约定：
- 使用 get_text("dict") 模式提取结构化文本块
- 根据字体大小和 block 类型推断 ElementType
- 纯图片 PDF（无可提取文本）抛出 ImageOnlyPDFError

约束：
- 不修改原始 PDF
- 坐标系使用 PDF 标准（左下角原点，pt 单位）
- 解析器版本参与幂等键

@see docs/architecture/adr/0006-parsed-bundle-evidence-schema.md
@module mentora/parsing/adapters/pymupdf
"""

import hashlib
import fitz  # PyMuPDF

from mentora.parsing.schemas import (
    BoundingBox,
    ElementType,
    Page,
    ParsedBundle,
    ParsedElement,
    ParserInfo,
    QualityInfo,
)
from mentora.parsing.adapters.exceptions import (
    CorruptedPDFError,
    EncryptedPDFError,
    ImageOnlyPDFError,
)


class PyMuPDFAdapter:
    """通过 PyMuPDF 解析文本 PDF，产出 ParsedBundle。"""

    # 字体大小阈值（pt），用于推断标题层级
    HEADING_FONT_THRESHOLD = 14.0

    def parse(self, file_path: str, parser_version: str) -> ParsedBundle:
        """打开 PDF、逐页提取、组装 ParsedBundle。"""
        content_hash = self._compute_hash(file_path)

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            msg = str(exc).lower()
            if "encrypted" in msg or "password" in msg:
                raise EncryptedPDFError(f"PDF 已加密: {file_path}") from exc
            raise CorruptedPDFError(f"PDF 无法打开: {file_path}") from exc

        if doc.is_encrypted:
            doc.close()
            raise EncryptedPDFError(f"PDF 已加密: {file_path}")

        try:
            pages: list[Page] = []
            total_elements = 0

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_dict = page.get_text("dict")
                # get_text("dict") 的 bbox 为左上角原点；契约要求 PDF 左下角原点
                page_height = page.rect.height
                elements = self._extract_elements(page_dict, page_height)

                page_warnings: list[str] = []
                if not elements:
                    page_warnings.append(f"第 {page_idx + 1} 页无可提取文本")

                pages.append(
                    Page(
                        page_number=page_idx + 1,
                        original_label=None,
                        elements=elements,
                        warnings=page_warnings,
                    )
                )
                total_elements += len(elements)

            # 全局质量：检查是否纯图片 PDF
            if total_elements == 0:
                doc.close()
                raise ImageOnlyPDFError(f"PDF 无可提取文本（可能是纯图片）: {file_path}")

            text_page_count = sum(1 for p in pages if p.elements)
            quality = QualityInfo(
                score=0.9 if text_page_count == len(pages) else 0.5,
                text_page_ratio=text_page_count / len(pages) if pages else 0.0,
                garbled_ratio=0.0,
            )

            bundle = ParsedBundle(
                source_version_id="",  # 由调用方注入
                parser=ParserInfo(name="pymupdf", version=parser_version),
                content_hash=content_hash,
                pages=pages,
                warnings=[],
                quality=quality,
            )
            return bundle

        finally:
            doc.close()

    # ---- private ----

    def _compute_hash(self, file_path: str) -> str:
        sha = hashlib.sha256()
        with open(file_path, "rb") as fh:
            while True:
                chunk = fh.read(8192)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    def _extract_elements(self, page_dict: dict, page_height: float) -> list[ParsedElement]:
        """从 PyMuPDF page dict 提取 ParsedElement 列表，按阅读顺序。"""
        elements: list[ParsedElement] = []
        blocks = page_dict.get("blocks", [])

        for block in blocks:
            block_type = block.get("type", -1)

            # 图片块
            if block_type == 1:
                bbox = self._to_pdf_bbox(block.get("bbox"), page_height)
                elements.append(
                    ParsedElement(
                        type=ElementType.IMAGE,
                        text="",
                        bbox=bbox,
                    )
                )
                continue

            # 文本块
            if block_type == 0:
                for line in block.get("lines", []):
                    element = self._line_to_element(line, page_height)
                    if element is not None:
                        elements.append(element)

        return elements

    def _line_to_element(self, line: dict, page_height: float) -> ParsedElement | None:
        """将单个文本行转换为 ParsedElement。"""
        spans = line.get("spans", [])
        if not spans:
            return None

        text = "".join(span.get("text", "") for span in spans).strip()
        if not text:
            return None

        bbox = self._to_pdf_bbox(line.get("bbox"), page_height)
        font_sizes = [span.get("size", 0) for span in spans if span.get("size")]
        max_font_size = max(font_sizes) if font_sizes else 0

        # 根据字体大小推断类型
        if max_font_size >= self.HEADING_FONT_THRESHOLD:
            heading_level = 1 if max_font_size >= 18 else 2
            return ParsedElement(
                type=ElementType.HEADING,
                text=text,
                bbox=bbox,
                heading_level=heading_level,
            )
        else:
            return ParsedElement(
                type=ElementType.PARAGRAPH,
                text=text,
                bbox=bbox,
            )

    @staticmethod
    def _to_pdf_bbox(rect: list[float] | None, page_height: float) -> BoundingBox | None:
        """
        PyMuPDF rect（左上角原点，y 向下）→ 契约 BoundingBox（PDF 左下角原点）。

        转换：y_pdf = page_height - y_top
        """
        if rect is None or len(rect) < 4:
            return None
        x0, y_top, x1, y_bottom = rect[0], rect[1], rect[2], rect[3]
        return BoundingBox(
            x0=x0,
            y0=page_height - y_bottom,
            x1=x1,
            y1=page_height - y_top,
        )
