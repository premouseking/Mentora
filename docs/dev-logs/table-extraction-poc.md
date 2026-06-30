# 表格提取 POC 调研报告

- 日期：2026-06-16
- PyMuPDF 版本：1.27.2
- 关联：`mentora/parsing/adapters/pymupdf.py` `_merge_tables()`

## API 概览

PyMuPDF `page.find_tables()` 通过检测页面中的**线条（ruling lines）**和**文本对齐**来识别表格。

| 属性/方法 | 说明 |
|---|---|
| `tabs.tables` | 检测到的表格列表 |
| `table.bbox` | 表格包围盒（PyMuPDF 坐标） |
| `table.row_count` | 行数 |
| `table.col_count` | 列数 |
| `table.header` | 表头信息（`external`/`in_body`/`none`） |
| `table.extract()` | 提取表格内容，返回 `list[list[str]]` |

## 检测能力

### 可检测

- Word/LaTeX 导出的原生线条表格（PDF 中包含 `draw_line` 绘制的边框）
- 有完整边框线的数据表格
- 行列结构清晰的网格

### 不可检测

- **HTML 嵌入表格**：`insert_htmlbox()` 渲染的 `<table>` 不被识别（HTML 渲染为字符，非 PDF 线条）
- **无线框表格**：仅靠文本对齐排列、无边框线的表格
- **扫描版 PDF 中的表格**：图片形式的表格需要 OCR
- **复杂合并单元格**：不规则跨行跨列的表格提取可能错位

## 当前实现

`_merge_tables()` 方法：

1. 调用 `page.find_tables()` 获取表格列表
2. 对每个表格，将 bbox 转换为 PDF 坐标系
3. 查找 bbox 中心点落在表格区域内的 `PARAGRAPH`/`HEADING` 元素
4. 用 `table.extract()` 结果（TSV 格式）替换这些元素为 `TABLE` 类型
5. `find_tables()` 不可用或无表格时保持原行为不变

输出格式：
```
TSV(3x3)
姓名	成绩	排名
张三	95	1
李四	87	2
```

## 已知限制

1. **依赖 PDF 原生线条**：HTML 嵌入和无线框表格无法检测
2. **pymupdf_layout 包**：PyMuPDF 提示安装 `pymupdf_layout` 可改善布局分析，当前未安装
3. **合并单元格**：`extract()` 对跨行跨列的单元格处理可能不完美
4. **表格内包含图片**：图片块不会被纳入 TABLE 元素

## 建议

1. 当前实现已覆盖最常见的 Word/LaTeX 原生表格场景
2. 后续可安装 `pymupdf_layout` 扩展检测范围（需额外 pip 依赖）
3. 扫描版 PDF 的表格依赖 OCR（P3 预研范围）
4. 表格作为结构化数据输出，EvidenceUnit 拆分时应跳过 TABLE 元素（文本已在 TSV 中，无需重复分段）
