# 解析基准测试报告

- 日期：2026-06-13
- 解析器：PyMuPDF v1.0.0
- 阶段：Stage 1 — P1-LH-03
- 关联：`docs/dev-log-2026-06-13-m2-m3.md`

## Fixture 概览

| Fixture | 页数 | 特征 | 文本密度 |
| --- | --- | --- | --- |
| `normal.pdf` | 1 | 中文正文 + 标题 | 高 |
| `headings.pdf` | 1 | 多级标题（16-20pt）+ 正文 | 中 |
| `multi_column.pdf` | 1 | 左右两栏中文文本 | 中 |

## 测试结果

| Fixture | 状态 | 页数 | 元素 | 证据 | 标题 | 段落 | 质量 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `headings.pdf` | 通过 | 1 | 5 | 3 | 2 | 3 | 0.90 |
| `multi_column.pdf` | 通过 | 1 | 3 | 3 | 0 | 3 | 0.90 |
| `normal.pdf` | 通过 | 1 | 3 | 2 | 1 | 2 | 0.90 |

- 全部 3 个 Fixture 通过（0 跳过，0 错误）
- 页码关联准确
- 标题/段落分类正确（基于字体大小阈值 14pt）
- 多栏 PDF 左右栏坐标差异保留（左栏 x0≈50，右栏 x0≈310）
- JSON 往返序列化/反序列化完整

## 已知限制

- **纯图片 PDF**：PyMuPDF 无法提取文本，正确抛出 `ImageOnlyPDFError`。
  纯图片 PDF 的 OCR 支持已延期至 Stage 2 以后。
- **表格/公式提取**：`get_text("dict")` 不区分表格和公式，当前均归类为 paragraph。
  结构化表格提取需引入 MinerU 或其他专用工具。
- **多列阅读顺序**：PyMuPDF 按 block 物理顺序提取，不会重新排序为正确的阅读顺序。
  多列文档的语义阅读顺序推断需在后续版本中实现。
- **加密 PDF**：正确识别加密状态，但当前密码输入入口未实现。

## 性能观察

- 单页 PDF（含 3-5 个元素）处理耗时 < 100ms
- 内存占用稳定在 ~15-25 MB 范围内
- 性能瓶颈在 PDF 打开阶段，线性扫描文本块几乎无开销

## 复现命令

```bash
cd apps/api
python -m mentora.parsing.benchmark
# 或通过 API：
curl http://localhost:8000/api/parsing/benchmark
```
