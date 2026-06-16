# Embedding 生成 + 向量搜索开发记录

- 日期：2026-06-16
- 关联架构：`docs/architecture/technical-solution.md` §6
- 前置：`docs/dev-log-2026-06-16-stage3.md`

## E1：Embedding Provider 适配层（2026-06-16）

### 做了什么

实现统一的 Embedding 生成接口，豆包（Doubao-1.5-Embedding）作为默认 Provider。

**选型依据：**
- 豆包在 C-MTEB 中文榜单排第一（74.76），超越 BGE-M3 和 OpenAI
- MRL 降维 2048→1024d，平衡性能与存储
- 火山引擎 API 国内直连，延迟低
- 费用 ~¥0.50/1M tokens，极低

**Provider 架构：**

```
EmbeddingProvider (Protocol)
├── DoubaoEmbeddingProvider   ← 当前实现
│   - 火山引擎 API v3
│   - MRL 降维 1024d
│   - 批量请求 (batch_size=100)
│   - 自动重试 (3 次)
│   - 维度/数量校验
└── (后续可扩展)
```

**核心函数：**

| 函数 | 说明 |
|---|---|
| `DoubaoEmbeddingProvider.embed(texts)` | 批量生成 embedding，顺序与输入一致 |
| `DoubaoEmbeddingProvider.dimensions` | 返回 1024 |
| `get_provider()` | 根据 settings 返回当前 Provider 实例 |

**Schema 变更：**
- `ChunkProjection.embedding`：1536d → 1024d
- `SentenceProjection.embedding`：1536d → 1024d
- IVFFlat 索引删除后重建（迁移 0004）

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/embedding_provider.py`（新建） | `EmbeddingProvider` Protocol + `DoubaoEmbeddingProvider` + `get_provider()` |
| `config/settings.py` | 新增 `EMBEDDING_*` 配置项（6 个） |
| `mentora/retrieval/models.py` | `ChunkProjection.embedding`、`SentenceProjection.embedding` 维度 1536→1024 |
| `mentora/retrieval/migrations/0004_*.py`（新建） | 向量维度迁移 |
| `apps/api/tests/test_embedding_provider.py`（新建） | 9 个测试 |

### 测试覆盖

1. `test_dimensions_property` — 维度属性
2. `test_empty_texts` — 空列表
3. `test_single_text` — 单文本 embedding
4. `test_batch_split` — 分批请求
5. `test_returns_in_order` — 结果顺序
6. `test_dimension_mismatch_raises` — 维度不匹配
7. `test_count_mismatch_raises` — 数量不匹配
8. `test_retry_on_error` — 网络错误重试
9. `test_all_retries_exhausted` — 重试耗尽

### 配置项

```bash
# .env 或环境变量
VOLCANO_ENGINE_API_KEY=your-api-key    # 豆包 API Key（火山引擎）
EMBEDDING_PROVIDER=doubao              # 默认值
EMBEDDING_DOUBAO_MODEL=doubao-embedding
EMBEDDING_DOUBAO_DIMENSIONS=1024
EMBEDDING_DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_embedding_provider.py -v
```

## 待完成

| 任务 | 说明 | 状态 |
|---|---|---|
| E2 | Chunk Embedding 生成 Celery 任务 | 待开始 |
| E3 | 向量搜索集成到 search() | 待 E1+E2 完成后 |
| E4 | 检索基准对比（三路 vs 两路） | 待 E3 完成后 |
