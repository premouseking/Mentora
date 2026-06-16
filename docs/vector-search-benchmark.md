# 向量搜索基准对比报告

- 日期：2026-06-16
- 关联：`mentora/retrieval/benchmark_vector.py`
- 豆包 Embedding：Doubao-1.5-Embedding, MRL 1024d

## 基准环境

| 项目 | 值 |
|---|---|
| 语料 | 11 EvidenceUnit（3 个 PDF fixture） |
| Chunk 数 | 3 个 |
| 已 Embed | 0（未配置 VOLCANO_ENGINE_API_KEY） |
| 金标查询 | 6 个（精确/模糊/缩写） |

## 当前结果（无 API Key，自动降级）

| 模式 | P@5 | P@10 | Recall | 延迟 |
|---|---|---|---|---|
| FTS + Trgm | 0.300 | 0.150 | 0.833 | 1.1ms |
| FTS + Trgm + Vector | 0.300 | 0.150 | 0.833 | 0.9ms |

> 当前「Chunk 已 Embed=0」，向量路在 `_search_vector()` 中检测到 API key 为空后立即返回 `{}`，两路和三路结果一致、延迟相当。**降级策略验证通过**：无 API key 时不影响基础检索。

## 预期提升（配置 API Key 后）

基于豆包 C-MTEB 榜首精度，预期：

- **语义相近查询**（如「高速缓存」→「Cache 存储原理」）：向量路补充 FTS 无法覆盖的语义变体，Recall 提升
- **缩写/口语查询**（如「组成原理」→「计算机组成原理」）：向量对齐语义空间，P@5 预期提升 5-10%
- **延迟增幅**：API 调用 ~100-200ms（国内直连），RRF 融合计算可忽略

## 如何启用

```bash
export VOLCANO_ENGINE_API_KEY="your-key"
cd apps/api
.venv/bin/python manage.py run_vector_benchmark
```

## 已知问题

1. 首次 `_search_vector()` 无 API key 时曾有 3.3s 延迟——因空 key 请求火山引擎 API 触发超时 + 重试（1s+2s=3s sleep）。已修复：`_search_vector()` 入口检查 API key 为空则直接返回 `{}`。
2. SentenceProjection 的 embedding 字段目前不生成（设计如此，按需求生成）。
