# 第二阶段开发记录：基于证据的课程问答

- 日期：2026-06-13
- 阶段：Stage 2（基于证据的课程问答）
- 关联架构：`docs/architecture/technical-solution.md` §6、`docs/project-management/delivery-roadmap.md`
- 关联 ADR：`docs/architecture/adr/0006-parsed-bundle-evidence-schema.md`

## S2-LH-01：引用定位服务（2026-06-13）

### 做了什么

实现引用定位服务 `locator.py`，将 Evidence ID 转换为前端可用的跳转坐标。

**核心函数：**

| 函数 | 输入 | 输出 |
|---|---|---|
| `locate_evidence()` | evidence_id (UUID) | CitationLocation：页码、bbox、正文、前后上下文、句级定位 |
| `locate_evidence_batch()` | evidence_ids (list) | {evidence_id: CitationLocation} 字典 |

**CitationLocation 字段：**

```python
@dataclass
class CitationLocation:
    evidence_id: str        # 稳定引用 ID
    page_number: int        # 页码（从 1 开始）
    bbox: dict | None       # {x0, y0, x1, y1} PDF pt 单位
    content: str            # 证据正文
    context_before: str | None   # 同页前一个 Evidence 的内容（最多 300 字）
    context_after: str | None    # 同页后一个 Evidence 的内容（最多 300 字）
    sentences: list[SentenceLocation]  # 句级定位
```

**设计决策：**

1. **上下文窗口不跨页**：`context_before`/`context_after` 通过 Django ORM 查询同 `source_version_id` 同 `page_number` 的相邻 EvidenceUnit，跨页截断
2. **句级定位按需生成**：调用 `repository.get_sentences_by_evidence()`，如果 SentenceProjection 表中无记录则返回空列表
3. **无效 ID 返回 None**：不抛异常，调用方自行处理空结果
4. **批量定位保持顺序**：`locate_evidence_batch()` 按输入顺序返回结果

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/locator.py` | 引用定位服务：单条 + 批量定位 |
| `apps/api/tests/test_locator.py` | 5 个测试：to_dict、最小定位、字段完整性、跨页截断、同页相邻 |

### 测试覆盖（全部 6 项通过）

1. `test_to_dict` — CitationLocation 序列化正确
2. `test_minimal_location` — 最小定位信息（无 bbox、无上下文、无句子）
3. `test_evidence_unit_fields_match_locator_expectations` — Pydantic EvidenceUnit 字段对接定位需求
4. `test_element_indices_reference_integrity` — element_indices 指向存在的 ParsedElement
5. `test_cross_page_context_boundary` — 跨页证据不互为上下文
6. `test_same_page_adjacent` — 同页相邻证据识别

### Bug 修复

- CitationLocation 的 `context_before`/`context_after`/`bbox`/`content` 补充默认值（缺省不抛 TypeError）
- ParsedBundle/EvidenceUnit/EvidenceSnapshot 的 `created_at` 从 `datetime.utcnow()` 迁移为 `datetime.now(timezone.utc)`，消除 Python 3.12+ 弃用警告
4. `test_cross_page_context_boundary` — 跨页证据不互为上下文
5. `test_same_page_adjacent` — 同页相邻证据识别

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_locator.py -v
```

---

## S2-LH-02：检索 API 端点（2026-06-13）

### 做了什么

实现两个 REST 端点，供 LWJ 的 Tutor 和 LBZ 的前端消费。

**端点：**

```
GET /api/retrieval/search?q=Cache映射&top_k=10
  → { query, total_candidates, elapsed_ms,
      results: [{ evidence_id, content_preview, page_number, score, fts_score, trgm_score }] }

GET /api/retrieval/evidence/<uuid>/location
  → CitationLocation.to_dict()
  → 404 if not found
```

**locator 增强：**

- 新增 `load_corpus()` 函数，支持内存语料库查找（无需 Django ORM）
- `locate_evidence()` 优先使用内存语料库，ORM 不可用时回退
- `_locate_from_corpus()` 在内存语料库中查找同页相邻证据

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/views.py` | search_view + locate_view，模块加载时注入语料库 |
| `config/urls.py` | 注册 `/api/retrieval/search` 和 `/api/retrieval/evidence/<uuid>/location` |
| `apps/api/tests/test_retrieval_views.py` | 9 个测试（搜索 6 + 定位 3） |
| `mentora/retrieval/locator.py` | 增强：新增内存语料库查找 |

### 测试覆盖

**搜索端点 (6)：**
1. 正常查询返回匹配结果
2. 空查询返回 400
3. 缺少 q 参数返回 400
4. top_k 限制结果数量
5. 每条结果含 score/fts/trgm/evidence_id/page_number/content_preview
6. 错别字容错（trgm 路兜底）

**定位端点 (3)：**
1. 有效 ID 返回完整定位（evidence_id/page_number/content）
2. 不存在的 ID 返回 404
3. 定位结果含 context_before/context_after

### 验证命令

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_retrieval_views.py -v
```

---

## S2-LH-03：PG 原生混合检索（2026-06-13）

### 做了什么

将 M5-B 的 Python 内存循环检索升级为真实 PostgreSQL FTS + pg_trgm SQL 查询。

**search.py 重写：**

| 函数 | 说明 |
|---|---|
| `search()` | 公开入口，自动检测 DB 可用性：可用 → `_search_pg()`，不可用 → `_search_memory()` |
| `_search_pg()` | PG 原生两路检索 + RRF 融合 |
| `_search_memory()` | 保留的 M5-B 内存版回退方案 |

**PG SQL 查询细节：**

```sql
-- FTS 路（权重 0.7）
SELECT id, ts_rank(to_tsvector('simple', content), 
       plainto_tsquery('simple', <jieba分词结果>)) AS rank
FROM retrieval_evidence_unit
WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', <query>)
ORDER BY rank DESC;

-- Trgm 路（权重 0.3）
SELECT id, similarity(content, <原始查询>) AS sim
FROM retrieval_evidence_unit
WHERE content % <原始查询>
ORDER BY sim DESC
LIMIT 50;
```

**设计决策：**
- 分词层（tokenizer.py + jieba_dict.txt）完全不动
- `build_fts_query()` 将 jieba 分词结果用 `&` 连接传给 PG
- Trgm 路用原始查询文本（不去分词，保留字符级容错）
- 三路权重和 RRF 融合逻辑与内存版完全一致
- views.py 无需修改 —— `search()` 自动选择 PG/内存

### 改动文件

| 文件 | 改动 |
|---|---|
| `mentora/retrieval/search.py` | 重写：拆分 `_search_pg()` + `_search_memory()`，`search()` 自动选择 |

### 验证命令

```bash
# 内存版（DB 不可用时自动回退）
cd apps/api
.venv/bin/python -m pytest tests/test_retrieval_views.py -v

# PG 版（Docker PostgreSQL 运行时）
docker exec docker-postgres-1 pg_isready -U mentora
.venv/bin/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()
from mentora.retrieval.search import search
rs = search('直接映射', top_k=3)
print(f'PG search: {len(rs.results)} results, {rs.elapsed_ms}ms')
"
```

---

## S2-LH-04：检索质量基准（真实数据）（2026-06-16）

### 做了什么

用 M3 PyMuPDF 解析产物填充 EvidenceUnit 表，对真实数据运行检索基准，输出 P@5/P@10/Recall 报告。

**核心流程：**
```
3 个 PDF Fixture → PyMuPDFAdapter.parse() → ParsedBundle
  → split_evidence() → EvidenceUnit（Pydantic）
  → 写入 retrieval_evidence_unit 表（PG）
  → 6 个金标查询 → _search_pg() 检索
  → 对比返回 ID vs 期望 ID → P@5/P@10/Recall
```

**基准结果：**

| 指标 | 值 |
|---|---|
| 语料库（3 PDF） | 11 EvidenceUnit |
| 平均 P@5 | 0.367 |
| 平均 Recall@10 | 0.917 |

### Bug 修复

- **中文文本提取乱码**：`fitz.insert_text()` 不支持 CJK 字体 → 改用 `page.insert_htmlbox()`
- **FTS 中文不匹配**：`to_tsvector('simple', ...)` 对中文逐字切分，无法匹配词 → 改用 jieba 分词 + `content ILIKE '%word%' AND ...`

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/retrieval/benchmark_runner.py` | 端到端基准：解析 → 入库 → 检索 → 评估 |
| `mentora/retrieval/management/commands/run_retrieval_benchmark.py` | Django 管理命令 |
| `docs/retrieval-benchmark-report.md` | 基准报告（含分析） |
| `mentora/retrieval/migrations/0002_*.py` | Django 自动生成的索引重命名迁移 |

### 改动文件

| 文件 | 改动 |
|---|---|
| `mentora/retrieval/search.py` | FTS 从 `to_tsvector` 改为 jieba + ILIKE（中文兼容） |
| `tests/fixtures/*.pdf` | 重新生成（`insert_htmlbox` 替代 `insert_text`） |

### 验证命令

```bash
cd apps/api
python manage.py run_retrieval_benchmark
```

---

## S2-LH-03 补充：中文检索方案升级 — jieba + tsvector + GIN 索引（2026-06-16）

### 问题

S2-LH-03 初始版本使用 `content ILIKE '%word%'` 做中文匹配——全表扫描，11 条数据无感知，数百条后延迟不可接受。

### 方案

**写入时 jieba 分词 + 存入 tsvector 列 + GIN 索引，查询时 `search_vector @@ tsquery` 走索引。**

```
写入路径：
  EvidenceUnit.content
    → jieba.cut() → "计算机系统 由 硬件 和 软件 组成"
    → 存入 segmented_content 列
    → SearchVector('segmented_content', config='simple') → search_vector 列
    → GIN 索引

查询路径：
  用户查询 "计算机系统概述"
    → jieba 分词 → plainto_tsquery('simple', '计算机系统 & 概述')
    → search_vector @@ query → GIN 索引查找
    → ts_rank() 排序
```

### 为什么 simple 配置这次有效

写入前 jieba 已在中文词间插入了空格（`"计算机系统 由 硬件"`），`simple` 配置按空格切分后每条 token 就是一个完整的中文词，不再是逐字拆分。

### 改动

| 文件 | 改动 |
|---|---|
| `models.py` | EvidenceUnit 新增 `segmented_content`、`search_vector` 字段 + GIN 索引 |
| `migrations/0003_add_segmented_search_vector.py` | 新增字段和索引的迁移 |
| `search.py` | FTS 路从 ILIKE 改为 `search_vector @@ plainto_tsquery('simple', ...)` + `ts_rank` 排序 |
| `benchmark_runner.py` | `_load_evidence_into_db()` 写入时自动生成 `segmented_content` 和 `search_vector` |

## 第二阶段总结

| 任务 | 说明 | 测试 | 状态 |
|---|---|---|---|
| S2-LH-01 | 引用定位服务 | 6/6 | ✓ |
| S2-LH-02 | 检索 API 端点 | 9/9 | ✓ |
| S2-LH-03 | PG 原生混合检索 | 9/9 + PG 验证 | ✓ |
| S2-LH-04 | 检索质量基准 | P@5=0.367 Recall=0.917 | ✓ |

LH 在第二阶段的四项任务全部完成。下一步需 WH 交付 Source/SourceVersion ORM 模型后，将 source_version_id 迁移为 FK；需 LWJ 确认 Embedding Provider 后接入 pgvector 向量检索路。

## 待完成（第二阶段后续）

| 任务 | 状态 | 说明 |
|---|---|---|
| S2-LH-02 检索 API 端点 | 待开始 | GET /api/retrieval/search + /evidence/:id/location |
| S2-LH-03 PG 原生混合检索 | 待开始 | M5-B 内存版升级为真实 PG SQL |
| S2-LH-04 检索质量基准 | 待开始 | 用 M3 解析产物填充 Evidence 表并评估 |
