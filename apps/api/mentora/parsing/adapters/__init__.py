"""
解析器适配器注册表。

约定：
- 每个适配器实现 parse(file_path: str, parser_version: str) -> ParsedBundle
- 通过文件扩展名或 MIME 类型路由到对应适配器
- 新增解析器时在此注册，不修改调用方代码

约束：
- 适配器不直接访问数据库或对象存储
- 异常必须转换为 ParsingError 子类
@module mentora/parsing/adapters
"""

from mentora.parsing.adapters.exceptions import (
    CorruptedPDFError,
    EncryptedPDFError,
    ImageOnlyPDFError,
    ParsingError,
    UnsupportedFormatError,
)
from mentora.parsing.adapters.pymupdf import PyMuPDFAdapter
from mentora.parsing.schemas import ParsedBundle

_ADAPTERS: dict[str, type] = {
    ".pdf": PyMuPDFAdapter,
}


def get_adapter(file_path: str):
    """根据文件扩展名返回解析器适配器实例。"""
    import os

    ext = os.path.splitext(file_path)[1].lower()
    adapter_cls = _ADAPTERS.get(ext)
    if adapter_cls is None:
        raise UnsupportedFormatError(f"不支持的文件格式: {ext}")
    return adapter_cls()


def parse(file_path: str, parser_version: str) -> ParsedBundle:
    """统一解析入口。"""
    adapter = get_adapter(file_path)
    return adapter.parse(file_path, parser_version)
