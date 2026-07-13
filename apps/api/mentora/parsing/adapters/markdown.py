"""
Markdown 解析适配器。

约定：
- 逐行解析，按标题/表格/代码块/列表/引用/图片/正文分类
- 无页码 (page_number=1)，无坐标 (bbox=None)，存行号 (extra={start_line, end_line})
- 图片存储外部 URL 到 extra.url，不走上传管线
- 行内标记（加粗/斜体/超链接/行内代码）去除标记保留文本

参考: LightRead markdown_processor.py (header splitting + line span tracking)
@module mentora/parsing/adapters/markdown
"""

import re
from hashlib import sha256

from mentora.parsing.schemas import (
    ElementType,
    Page,
    ParsedBundle,
    ParsedElement,
    ParserInfo,
    QualityInfo,
)


# 行内标记正则
_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]+\)')       # [text](url) → text
_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')     # ![alt](url) → url
_BOLD_RE = re.compile(r'\*\*([^*]+)\*\*')             # **text** → text
_ITALIC_RE = re.compile(r'\*([^*]+)\*')               # *text* → text
_INLINE_CODE_RE = re.compile(r'`([^`]+)`')            # `code` → code
_TABLE_SEP_RE = re.compile(r'^\s*\|?[:\-\s|]+\|?\s*$')  # |---|---| 分隔行


def _compute_hash(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def _parse_inline(text: str) -> str:
    """去除行内标记，保留纯文本。"""
    text = _BOLD_RE.sub(r'\1', text)
    text = _ITALIC_RE.sub(r'\1', text)
    text = _INLINE_CODE_RE.sub(r'\1', text)
    text = _LINK_RE.sub(r'\1', text)
    return text.strip()


def _extract_images(text: str) -> list[str]:
    """提取行内图片 URL。"""
    return [m[1] for m in _IMG_RE.findall(text)]


def _is_hr(line: str) -> bool:
    return bool(re.match(r'^[-*_]{3,}\s*$', line))


class MarkdownAdapter:
    """Markdown 文件 → ParsedBundle。"""

    def parse(self, file_path: str, parser_version: str) -> ParsedBundle:
        with open(file_path, encoding="utf-8") as fh:
            content = fh.read()

        content_hash = _compute_hash(content)
        elements = self._parse_content(content)
        page = Page(page_number=1, original_label=None, elements=elements, warnings=[])

        return ParsedBundle(
            source_version_id="",
            parser=ParserInfo(name="markdown", version=parser_version),
            content_hash=content_hash,
            pages=[page] if elements else [],
            warnings=[],
            quality=QualityInfo(score=0.9, text_page_ratio=1.0, garbled_ratio=0.0),
        )

    def _parse_content(self, content: str) -> list[ParsedElement]:
        lines = content.replace("\r\n", "\n").split("\n")
        elements: list[ParsedElement] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # 空行
            if not stripped:
                i += 1
                continue

            # 水平线
            if _is_hr(stripped):
                i += 1
                continue

            # 代码块 ```
            if stripped.startswith("```"):
                start_line = i + 1
                i += 1
                code_lines = []
                while i < n and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # 跳过闭合 ```
                if code_lines:
                    elements.append(ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="\n".join(code_lines),
                        extra={"start_line": start_line, "end_line": i},
                    ))
                continue

            # 标题 #
            heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = _parse_inline(heading_match.group(2))
                elements.append(ParsedElement(
                    type=ElementType.HEADING,
                    text=text,
                    heading_level=level,
                    extra={"start_line": i + 1, "end_line": i + 1},
                ))
                i += 1
                continue

            # 表格 |...|...|
            if stripped.startswith("|") and stripped.endswith("|"):
                table_start = i
                table_rows = []
                while i < n:
                    s = lines[i].strip()
                    if not (s.startswith("|") and s.endswith("|")):
                        break
                    if not _TABLE_SEP_RE.match(s):
                        cells = [c.strip() for c in s[1:-1].split("|")]
                        for ci in range(len(cells)):
                            cells[ci] = _parse_inline(cells[ci])
                        table_rows.append(cells)
                    i += 1
                if table_rows:
                    tsv = "\n".join("\t".join(row) for row in table_rows)
                    elements.append(ParsedElement(
                        type=ElementType.TABLE,
                        text=tsv,
                        extra={"start_line": table_start + 1, "end_line": i},
                    ))
                continue

            # 图片 (独立行)
            img_urls = _extract_images(stripped)
            if img_urls and _parse_inline(stripped) == "":
                for url in img_urls:
                    elements.append(ParsedElement(
                        type=ElementType.IMAGE,
                        text="",
                        extra={"url": url, "start_line": i + 1, "end_line": i + 1},
                    ))
                i += 1
                continue

            # 引用 >
            if stripped.startswith(">"):
                quote_start = i + 1
                quote_lines = []
                while i < n and lines[i].strip().startswith(">"):
                    text = _parse_inline(lines[i].strip()[1:].strip())
                    if text:
                        quote_lines.append(text)
                    i += 1
                if quote_lines:
                    elements.append(ParsedElement(
                        type=ElementType.PARAGRAPH,
                        text="\n".join(quote_lines),
                        extra={"start_line": quote_start, "end_line": i},
                    ))
                continue

            # 列表 -
            if re.match(r'^-\s+', stripped):
                while i < n and re.match(r'^-\s+', lines[i].strip()):
                    text = _parse_inline(re.sub(r'^-\s+', '', lines[i].strip()))
                    elements.append(ParsedElement(
                        type=ElementType.LIST_ITEM,
                        text=text,
                        extra={"start_line": i + 1, "end_line": i + 1},
                    ))
                    i += 1
                continue

            # 正文段落
            para_start = i + 1
            para_lines = []
            while i < n and lines[i].strip() and not lines[i].strip().startswith(("#", ">", "-", "|", "```")):
                text = _parse_inline(lines[i].strip())
                if text:
                    para_lines.append(text)
                i += 1
            if para_lines:
                elements.append(ParsedElement(
                    type=ElementType.PARAGRAPH,
                    text="\n".join(para_lines),
                    extra={"start_line": para_start, "end_line": i},
                ))

        return elements
