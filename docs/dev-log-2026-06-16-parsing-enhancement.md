# 解析增强开发记录

- 日期：2026-06-16
- 关联架构：`docs/architecture/technical-solution.md` §5
- 前置：`docs/dev-log-2026-06-13-m2-m3.md`

## P1：多列阅读顺序恢复（2026-06-16）

### 做了什么

修复 PyMuPDF 按物理 block 顺序提取导致多列 PDF 左右栏内容交错的问题。

**核心算法：**

1. 收集所有 ParsedElement 的 bbox.x0 值
2. 若 x0 跨度 < 页宽 30% → 单栏，不重排
3. 找 x0 值序列中的最大自然间隙（1D 聚类），间隙中点为分栏线
4. 间隙 > 页宽 5% 才视为有效分栏，否则单栏
5. 每栏内按 y0 降序排列（PDF 左下角原点，y 越大越靠上 → 从上到下阅读顺序）
6. 检测 3+ 栏时向 ParsedBundle.warnings 追加警告

**设计决策：**
- 用最大间隙法而非中位数法：中位数在左右栏元素数不均时会被拉入多的那组，导致一侧为空
- 3+ 栏不强行递归拆分——复杂排版的阅读顺序语义不确定，标记警告、尽力按左→右输出

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/parsing/adapters/column_reorder.py`（新建） | `reorder_elements()` + `_find_split_point()` |
| `mentora/parsing/adapters/pymupdf.py` | 修改：`_extract_elements` 改为返回 `tuple[list, list]`，末尾调用 `reorder_elements`；`parse()` 传递 `page_width` |
| `apps/api/tests/test_column_reorder.py`（新建） | 9 个测试 |

### 测试覆盖

1. `test_similar_x0_preserves_order` — 单栏 x0 集中，保持原序
2. `test_narrow_range_no_split` — x0 跨度不足 30% 页宽，不重排
3. `test_left_then_right` — 双栏：左栏完整在前，右栏在后
4. `test_small_gap_treated_as_single` — 栏间间隙不足 5% 页宽，视为单栏
5. `test_three_columns_warns` — 三栏产生警告
6. `test_empty_list` — 空列表
7. `test_single_element` — 单元素
8. `test_no_bbox_elements_at_end` — 无 bbox 元素保持末尾
9. `test_y0_descending_within_column` — 栏内 y0 降序验证

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_column_reorder.py -v
```

## 待完成

| 任务 | 说明 | 状态 |
|---|---|---|
| P2 | 表格提取 POC | 待开始 |
| P3 | OCR 方案预研 | 待 P1 完成后 |
