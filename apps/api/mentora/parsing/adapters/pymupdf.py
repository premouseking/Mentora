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
from mentora.parsing.adapters.column_reorder import reorder_elements
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
                page_width = page.rect.width
                elements, reorder_warnings = self._extract_elements(
                    page, page_dict, page_height, page_width
                )

                page_warnings: list[str] = list(reorder_warnings)

                page_warnings: list[str] = list(reorder_warnings)
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

            # 全局质量：纯图片 PDF 尝试 OCR 回退
            if total_elements == 0:
                from mentora.parsing.adapters.ocr import TesseractOCRAdapter

                ocr = TesseractOCRAdapter()
                if not ocr.is_available():
                    doc.close()
                    raise ImageOnlyPDFError(
                        f"PDF 无可提取文本且 OCR 不可用: {file_path}"
                    )

                for page_idx in range(len(doc)):
                    ocr_text = ocr.ocr_page(doc[page_idx])
                    # 重新计算页高以生成 bbox（全页文本）
                    page_height = doc[page_idx].rect.height
                    if ocr_text:
                        pages[page_idx].elements.append(
                            ParsedElement(
                                type=ElementType.PARAGRAPH,
                                text=ocr_text,
                                bbox=BoundingBox(
                                    x0=0, y0=0,
                                    x1=doc[page_idx].rect.width,
                                    y1=page_height,
                                ),
                            )
                        )
                total_elements = sum(len(p.elements) for p in pages)

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

    def _extract_elements(
        self,
        fitz_page,
        page_dict: dict,
        page_height: float,
        page_width: float,
    ) -> tuple[list[ParsedElement], list[str]]:
        """从 PyMuPDF page 提取 ParsedElement 列表，按阅读顺序。"""
        elements: list[ParsedElement] = []
        blocks = page_dict.get("blocks", [])

        for block in blocks:
            block_type = block.get("type", -1)

            # 图片块：记录 xref 供 processing 管道提取
            if block_type == 1:
                bbox = self._to_pdf_bbox(block.get("bbox"), page_height)
                xref = self._find_image_xref(fitz_page, block)
                extra = {"xref": xref} if xref is not None else None
                elements.append(
                    ParsedElement(
                        type=ElementType.IMAGE,
                        text="",
                        bbox=bbox,
                        extra=extra,
                    )
                )
                continue

            # 文本块
            if block_type == 0:
                for line in block.get("lines", []):
                    element = self._line_to_element(line, page_height)
                    if element is not None:
                        elements.append(element)

        # 表格检测：将表格区域内的文本元素合并为 TABLE 元素
        elements, table_warnings = self._merge_tables(fitz_page, elements, page_height)

        # 多列阅读顺序恢复
        elements, reorder_warnings = reorder_elements(elements, page_width)
        return elements, table_warnings + reorder_warnings

    @staticmethod
    def _find_image_xref(page, block: dict) -> int | None:
        """根据图片 block 匹配 PDF 内嵌图片的 xref 编号。"""
        block_bbox = block.get("bbox")
        if not block_bbox:
            return None
        bx0, by0, bx1, by1 = block_bbox
        for img in page.get_image_info():
            i_bbox = img.get("bbox")
            if not i_bbox:
                continue
            ix0, iy0, ix1, iy1 = i_bbox
            # bbox 重叠度 > 50%
            overlap_x = max(0, min(bx1, ix1) - max(bx0, ix0))
            overlap_y = max(0, min(by1, iy1) - max(by0, iy0))
            if overlap_x * overlap_y > 0:
                return img.get("xref")
        return None

    def _merge_tables(
        self,
        fitz_page,
        elements: list[ParsedElement],
        page_height: float,
    ) -> tuple[list[ParsedElement], list[str]]:
        """
        检测页面中的表格，将表格区域内的文本元素替换为 TABLE 类型元素。

        表格文本以 TSV 格式存储：制表符分隔列，换行分隔行。
        """
        warnings: list[str] = []
        try:
            tabs = fitz_page.find_tables()
        except Exception:
            # find_tables 不可用时跳过
            return elements, warnings

        if not tabs or not tabs.tables:
            return elements, warnings

        table_elements: list[ParsedElement] = []
        used_indices: set[int] = set()

        for table in tabs.tables:
            # 转换表格 bbox 到 PDF 坐标系
            table_bbox = self._to_pdf_bbox(
                list(table.bbox), page_height
            )
            if table_bbox is None:
                continue

            # 收集 bbox 中心点在表格区域内的文本元素
            cell_indices: list[int] = []
            for i, el in enumerate(elements):
                if i in used_indices or el.bbox is None:
                    continue
                if el.type not in (ElementType.PARAGRAPH, ElementType.HEADING):
                    continue
                cx = (el.bbox.x0 + el.bbox.x1) / 2
                cy = (el.bbox.y0 + el.bbox.y1) / 2
                if (
                    table_bbox.x0 <= cx <= table_bbox.x1
                    and table_bbox.y0 <= cy <= table_bbox.y1
                ):
                    cell_indices.append(i)

            if not cell_indices:
                continue

            # 用 find_tables 提取的结构化内容代替文本行内容
            try:
                rows = table.extract()
            except Exception:
                rows = []
            if rows:
                tsv_text = "\n".join("\t".join(str(cell) for cell in row) for row in rows)
                prefix = f"TSV({table.row_count}x{table.col_count})\n"
            else:
                # 回退：合并区域内元素文本
                tsv_text = "\n".join(
                    elements[i].text for i in cell_indices
                )
                prefix = ""

            table_elements.append(
                ParsedElement(
                    type=ElementType.TABLE,
                    text=prefix + tsv_text,
                    bbox=table_bbox,
                )
            )
            used_indices.update(cell_indices)

        # 未被表格覆盖的元素 + 新表格元素，按原序排列
        result = [
            el for i, el in enumerate(elements)
            if i not in used_indices
        ]
        # 在第一个被替换元素的位置插入表格元素
        if table_elements:
            first_used = min(used_indices)
            insert_pos = sum(
                1 for i in range(first_used) if i not in used_indices
            )
            for te in table_elements:
                result.insert(insert_pos, te)
                insert_pos += 1

        return result, warnings

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
        # 容错：某些 PDF 元素坐标异常，交换确保 x1 >= x0, y1 >= y0
        x0, x1 = min(x0, x1), max(x0, x1)
        y0 = max(0.0, page_height - y_bottom)
        y1 = min(page_height, page_height - y_top)
        if x1 <= x0 or y1 <= y0:
            return None
        return BoundingBox(
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
        )
