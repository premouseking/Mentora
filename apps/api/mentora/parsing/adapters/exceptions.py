"""解析异常类，避免循环导入。"""


class ParsingError(Exception):
    """解析失败基类。"""


class UnsupportedFormatError(ParsingError):
    """不支持的文件格式。"""


class EncryptedPDFError(ParsingError):
    """加密 PDF，无法解析。"""


class CorruptedPDFError(ParsingError):
    """损坏的 PDF 文件。"""


class ImageOnlyPDFError(ParsingError):
    """纯图片 PDF，无可提取文本。"""
