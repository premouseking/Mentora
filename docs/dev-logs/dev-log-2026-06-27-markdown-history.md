# Markdown 解析 + 学习记录模块开发记录

- 日期：2026-06-27
- 关联：`docs/architecture/module-boundaries.md`

## Markdown 解析适配器

### 实现

参考 LightRead `markdown_processor.py` + `text_spliter.py`，自建无 langchain 依赖的 MarkdownAdapter。

### 支持的元素

| MD 语法 | ParsedElement Type |
|---|---|
| `# 标题` ~ `###### 标题` | HEADING(level=1-6) |
| `\| 列1 \| 列2 \|` | TABLE(TSV) |
| `> 引用` | PARAGRAPH（去 `>` 标记） |
| ` ```code``` ` | PARAGRAPH（原样保留） |
| `- 列表项` | LIST_ITEM |
| `[text](url)` | PARAGRAPH（保留 text，去除 url） |
| `![alt](url)` | IMAGE(extra.url=url) |
| `**加粗**` `*斜体*` | PARAGRAPH（去除标记） |

### 行号追踪

每个 `ParsedElement.extra` 记录 `{start_line, end_line}`，供前端在原文中定位高亮。

### 图片处理

MD 图片存 URL 到 `extra.url`，不走上传管线。evidence 中 MD 图片的 `content` 直接存 URL，PDF 图片的 `content` 存 `[图片]` + `artifact_ref` 指向 MinIO。

### 注册

`adapters/__init__.py`：`.md` / `.markdown` → MarkdownAdapter

### 分块复用

已有 `chunk_builder.py` 的结构感知切分（heading 触发分界）直接适用于 MD 解析产物，零额外代码。

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/parsing/adapters/markdown.py`（新建） | MarkdownAdapter（200+ 行） |
| `mentora/parsing/adapters/__init__.py` | 注册 .md/.markdown |
| `mentora/parsing/evidence.py` | IMAGE 处理兼容 MD URL |

---

## 学习记录模块（H1-H3）

### H1：LearningHistoryEvent ORM

`mentora/learning/models.py` 新增 `LearningHistoryEvent`：

| 字段 | 说明 |
|---|---|
| course_id | 课程 ID |
| event_type | 12 种事件类型 |
| title / detail / result | 展示字段 |
| task_id / phase_id | 关联字段 |
| created_at | 时间索引 |

### H2：API + 服务

`GET /api/history/?courseId=xxx&limit=50`

| 函数 | 说明 |
|---|---|
| `get_history(course_id)` | 查询 + 格式化为前端字段 |
| `write_history_event(...)` | 写入事件（各模块调用） |

### H3：写入点接入

| 触发 | 事件 | 文件 |
|---|---|---|
| `complete_task()` | task_completed | `learning/services` |
| `submit_attempt()` | quiz_attempted | `assessment/services` |
| `upload_complete()` | source_added | `knowledge/views` |
| `course_activate()` | course_started | `courses/services` |

暂缓：task_started / check_passed / check_failed / stage_changed / plan_adjusted / skill_mastered / course_paused。

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/learning/models.py` | LearningHistoryEvent ORM |
| `mentora/learning/services/__init__.py` | get_history + write_history_event + complete_task 写入 |
| `mentora/learning/views.py`（新建） | history_list 端点 |
| `mentora/assessment/services/__init__.py` | submit_attempt 写入 |
| `mentora/knowledge/views.py` | upload_complete 写入 |
| `mentora/courses/services/__init__.py` | course_activate 写入 |
| `config/urls.py` | /api/history/ 路由 |
