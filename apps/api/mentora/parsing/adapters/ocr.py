"""
Tesseract OCR 适配器：纯图片 PDF 的文本提取回退方案。

约定：
- 仅当 PyMuPDF 文本提取结果为空时调用（total_elements == 0）
- Tesseract 不可用时维持原有 ImageOnlyPDFError
- 单页 150 DPI 约 3s，chi_sim+eng 中英双语识别

参考: LightRead ocr_router.py (Tesseract CPU + PyMuPDF 渲染)
@module mentora/parsing/adapters/ocr
"""


class TesseractOCRAdapter:
    """Tesseract OCR 适配器。

    PyMuPDF 渲染 PDF 页为图片 → pytesseract OCR → 文本。
    """

    def __init__(self, lang: str = "chi_sim+eng", dpi: int = 150):
        self._lang = lang
        self._dpi = dpi

    def ocr_page(self, page) -> str:
        """对单个 PDF 页面执行 OCR，返回识别文本。"""
        import fitz
        from PIL import Image

        import pytesseract

        zoom = self._dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return pytesseract.image_to_string(img, lang=self._lang).strip()

    def is_available(self) -> bool:
        """检测 Tesseract 是否可用。"""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
