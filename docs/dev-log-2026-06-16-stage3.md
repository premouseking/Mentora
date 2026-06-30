# 检索增强开发记录

- 日期：2026-06-16
- 关联架构：`docs/architecture/technical-solution.md` §6
- 关联 ADR：`docs/architecture/adr/0006-parsed-bundle-evidence-schema.md`

## R1：SentenceProjection 拆分器（2026-06-16）

### 做了什么

实现 EvidenceUnit.content → SentenceProjection 的自动拆分。

**核心函数：**

| 函数 | 输入 | 输出 |
|---|---|---|
| `split_sentences()` | content (str) | 句子列表 |
| `generate_sentence_projections()` | evidence_unit_id + content | SentenceProjection ORM 实例列表（未 save） |

**拆分规则：**
- 中文标点（。！？；\\n）作为句子边界
- 英文句尾标点（. ! ? 后跟空格+大写/行尾）作为句子边界
- 小数点和版本号（`0.95`、`v1.0`）中的点号不被误切
- 以句末标点（。！？；.!?）结尾的短句保留不合并
- 仅对无句末标点的过短碎片（<5 字符）合并到相邻句

**设计决策：**
- 不修改原始文本内容
- 三字符短句如「好。」保留（完成语义单位）
- 数字中的点号用占位符保护后正则切分，切分完成后恢复

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/sentence_splitter.py` | `split_sentences()` + `generate_sentence_projections()` |
| `apps/api/tests/test_sentence_splitter.py` | 9 个测试（拆分 8 + 生成 1） |

### 测试覆盖

1. `test_simple_chinese` — 中文句号拆分
2. `test_chinese_semicolon_and_newline` — 分号和换行
3. `test_keeps_english_period_in_decimal` — 小数和版本号保护
4. `test_mixed_chinese_english` — 中英混合
5. `test_empty_string` — 空字符串
6. `test_whitespace_only` — 纯空白
7. `test_merges_short_fragments` — 短句合并（句末标点不合并）
8. `test_generates_correct_count` — position_index 正确性
9. `test_filters_empty_sentences` — 空内容

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_sentence_splitter.py -v
```

---

## R2：ChunkProjection 生成器（2026-06-16）

### 做了什么

实现 EvidenceUnit 列表 → ChunkProjection 的滑动窗口聚合。

**核心函数：**

| 函数 | 输入 | 输出 |
|---|---|---|
| `estimate_tokens()` | text (str) | int |
| `build_chunks()` | evidence_units list, chunk_size=512, overlap=1 | ChunkProjection ORM 实例列表（未 save） |

**滑动窗口策略：**
- 累积 EvidenceUnit 直到 token 预估数 ≤ 512 → 输出一个 Chunk
- 相邻 Chunk 重叠 1 个 EvidenceUnit（保证上下文连续性）
- 第一个 unit 即使超过 chunk_size 也放入（避免死循环）
- Token 估算：中文 ~1.5 char/token，英文/数字 ~4 char/token

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/chunk_builder.py` | `estimate_tokens()` + `build_chunks()` |
| `apps/api/tests/test_chunk_builder.py` | 8 个测试（估算 3 + Chunk 生成 5） |

### 测试覆盖

1. `test_pure_chinese` — 纯中文 token 估算
2. `test_mixed_chinese_english` — 中英混合
3. `test_short_text_min_one` — 短文本至少返回 1
4. `test_single_unit` — 单个 EvidenceUnit → 1 Chunk
5. `test_multiple_small_units_one_chunk` — 多小 unit 合并
6. `test_large_units_split` — 超 chunk_size 拆分
7. `test_overlap_between_chunks` — 相邻 Chunk 重叠
8. `test_empty_list` — 空列表返回空
9. `test_chunk_content_preserved` — 内容拼接正确

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_chunk_builder.py -v
```

### Bug 修复

- **重叠逻辑错误**：`next_i = max(i + 1, j - overlap)` 在单 unit 填满整个 Chunk 时无法回退。改为 `next_i = j - overlap if j - overlap > i else j`——只有当上一 Chunk 包含 ≥2 个 unit 时才回退 overlap 个，否则从 j 继续。
- **测试数据不合理**：原测试每个 unit 100 tokens 正好等于 chunk_size，每 Chunk 只能装 1 个 unit，无法产生重叠。改为每 unit ~21 tokens / chunk_size=80，确保重叠可验证。

---

## R3：检索质量对比基准（2026-06-16）

### 做了什么

用同一套金标查询对比 EvidenceUnit / ChunkProjection / SentenceProjection 三种粒度的检索精度。

### 基准结果

| 粒度 | 数量 | P@5 | P@10 | Recall | 角色定位 |
|---|---|---|---|---|---|
| **EvidenceUnit** | 11 | 0.367 | 0.183 | 0.917 | 通用均衡检索 |
| **ChunkProjection** | 3 | 0.267 | 0.133 | **1.000** | RAG 上下文窗口 |
| **SentenceProjection** | 16 | **0.433** | **0.233** | 0.889 | 精确引用定位 |

### 分析

- **Chunk Recall=1.0**：滑动窗口策略有效，所有预期结果都在 Chunk 中。P@5 低是因为粒度粗（每 Chunk 装 3-4 条证据），实际 RAG 场景 top-3 即够用
- **Sentence P@5 最高**：句子短、匹配噪声少，适合「点击引用跳转到原文位置」
- **Evidence 均衡**：段落级检索在精度和召回之间取得平衡
- 三粒度互补符合架构文档 §6 的设计意图

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/benchmark_compare.py` | 三粒度对比基准：解析 → 入库三表 → 金标查询 → 评估 |
| `mentora/retrieval/management/commands/run_granularity_benchmark.py` | Django 管理命令 |

### 验证命令

```bash
cd apps/api
.venv/bin/python manage.py run_granularity_benchmark
```

## 检索增强总结

| 任务 | 说明 | 测试 | 状态 |
|---|---|---|---|
| R1 | SentenceProjection 拆分器 | 9/9 | ✓ |
| R2 | ChunkProjection 生成器 | 9/9 | ✓ |
| R3 | 检索质量对比基准 | 三粒度对比 | ✓ |

整条「PDF → EvidenceUnit → Chunk/Sentence → 检索」链路已完整。

## 待完成

| 任务 | 说明 | 状态 |
|---|---|---|
| R2 | ChunkProjection 生成器 | 待开始 |
| R3 | 检索质量对比基准 | 待 R1+R2 完成后 |
