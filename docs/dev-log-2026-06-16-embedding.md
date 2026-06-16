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

> Embedding + 向量搜索阶段（E1-E4）全部完成。
> 需配置 `VOLCANO_ENGINE_API_KEY` 后运行 `manage.py run_vector_benchmark` 获取有意义的对比数据。

---

## E4：检索基准对比（2026-06-16）

### 做了什么

创建向量搜索基准对比脚本，量化三路 RRF 对检索质量的提升。

**对比方案：**
- 两路（vector_weight=0）：FTS 0.7 + Trgm 0.3
- 三路（vector_weight=0.3）：FTS 0.5 + Trgm 0.2 + Vector 0.3

**当前结果（无 API Key，向量路自动降级）：**

| 模式 | P@5 | P@10 | Recall | 延迟 |
|---|---|---|---|
| FTS + Trgm | 0.300 | 0.150 | 0.833 | 1.1ms |
| FTS + Trgm + Vector | 0.300 | 0.150 | 0.833 | 0.9ms |

> 无 API key 时降级策略验证通过：两路三路结果一致、延迟相当。
> 配置 `VOLCANO_ENGINE_API_KEY` 后预期语义相近查询 Recall 提升 5-10%。

详见 `docs/vector-search-benchmark.md`。

### 期间修复

- **_search_vector() 无 API key 延迟问题**：空 key 导致 API 超时+重试（~3.3s/查询）。在入口处加 API key 为空检查，直接返回 `{}`，降级延迟降至 <1ms。

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/benchmark_vector.py`（新建） | 向量基准对比脚本：入库→Chunk→Embed→两路vs三路评估 |
| `mentora/retrieval/management/commands/run_vector_benchmark.py`（新建） | Django 管理命令 |
| `mentora/retrieval/search.py` | `_search_vector()` 增加 API key 空值快速降级 |
| `docs/vector-search-benchmark.md`（新建） | 基准对比报告 |
| `apps/api/tests/test_search_vector.py` | 适应 API key 检查逻辑的测试更新 |

### 验证命令

```bash
cd apps/api
.venv/bin/python manage.py run_vector_benchmark
```

---

## E3：向量搜索集成到 search()（2026-06-16）

### 做了什么

将 pgvector 向量相似度检索作为第三条通路接入 RRF 融合，实现 FTS + Trgm + Vector 三路混合检索。

**核心改动：**

1. 新增 `_search_vector()`：生成 query embedding → `search_chunks_by_vector()` → Chunk cosine distance 映射回 EvidenceUnit ID
2. `_search_pg()` 改为三路 RRF 融合，默认权重 `FTS=0.5, Trgm=0.2, Vector=0.3`
3. Provider 不可用（API key 未配置等）时 `_search_vector()` 返回空 dict，自动降级为两路
4. `search()` 新增 `vector_weight`（0=跳过向量路）和 `source_version_ids` 参数
5. `SearchResult.vector_score` 从恒 0 变为实际向量相似度分数

**降级策略：** `_search_vector()` 内部 catch 所有异常返回 `{}`——无 API key、网络不可用、无 embedding 数据时均自动回退，不影响基础检索功能。

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/search.py` | 新增 `_search_vector()`；`_search_pg()` 三路融合；`search()` 签名扩展；`_search_memory()` 签名兼容 |
| `apps/api/tests/test_search_vector.py`（新建） | 6 个测试 |

### 测试覆盖

1. `test_returns_empty_when_no_provider` — provider 不可用时返回空
2. `test_returns_chunk_to_evidence_mapping` — Chunk→Evidence 映射正确
3. `test_empty_chunks_returns_empty` — 无匹配 Chunk
4. `test_search_vector_weight_zero_skips_provider` — weight=0 跳过向量路
5. `test_search_preserves_new_params` — 新参数传递正常
6. `test_search_default_weights_no_error` — 默认权重不报错

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_search_vector.py -v
```

## E2：Chunk Embedding 生成 Celery 任务（2026-06-16）

### 做了什么

实现 `generate_chunk_embeddings` Celery 任务，处理解析→建 Chunk→生成 embedding 的最后一步。

**任务流程：**

1. 查询 `ChunkProjection` 中 `embedding IS NULL` 的记录（可选按 `source_version_id` 过滤）
2. 按 `batch_size=100` 分批调用 `get_provider().embed()`
3. `bulk_update` 批量写回
4. 已有 embedding 的 Chunk 跳过（幂等）
5. Provider 异常时记录 error 计数，不中断后续批次

**Celery 配置：** `max_retries=3`、`default_retry_delay=30`、`autoretry_for=(IOError, OSError, RuntimeError)`

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/tasks.py`（新建） | `generate_chunk_embeddings` Celery 任务 |
| `config/settings.py` | 新增 `mentora.retrieval.tasks.*` → heavy 队列路由 |
| `apps/api/tests/test_embedding_tasks.py`（新建） | 5 个测试（含 DB） |

### 测试覆盖

1. `test_empty_no_chunks` — 无 Chunk 时返回 processed=0
2. `test_generates_embeddings` — 为 3 个 Chunk 生成 1024d 向量并写回
3. `test_skips_existing_embeddings` — 已有 embedding 的跳过
4. `test_handles_provider_error` — API 异常记录 errors 不中断
5. `test_all_source_versions_when_none` — source_version_id=None 处理全部

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_embedding_tasks.py -v
```
