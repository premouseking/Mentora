# Sources 模块 + Topics 模块开发记录

- 日期：2026-06-26
- 关联：`docs/architecture/module-boundaries.md`

## Sources 模块（S1-S5）

### S1-S5 概要

| 任务 | 功能 | 端点 |
|---|---|---|
| S1 | 文件夹管理 | folder CRUD (4) + source move (1) |
| S2 | 标签管理 | update tags + list tags (2) |
| S3 | 资料归档 | archive + unarchive (2) |
| S4 | 模糊搜索 | list_sources 加 q 参数 (1) |
| S5 | 列表过滤 | list_sources 支持 6 种过滤 |

### 资料库 API（15 端点）

```
上传:    POST /api/uploads/           → 创建上传会话
         POST /api/uploads/complete/  → 完成上传，触发解析

资料:    GET  /api/library/sources/            → 列表（支持 6 种过滤）
         GET  /api/library/sources/<id>/       → 详情 + ParsedBundle
         DELETE /api/library/sources/<id>/     → 删除
         POST /api/library/sources/<id>/reparse/ → 重解析

标签:    PATCH /api/library/sources/<id>/tags/ → 更新标签
         GET  /api/library/tags/               → 列出所有标签

归档:    PATCH /api/library/sources/<id>/archive/   → 归档
         PATCH /api/library/sources/<id>/unarchive/ → 取消归档

移动:    PATCH /api/library/sources/<id>/move/ → 移入/移出文件夹

文件夹:  POST   /api/library/folders/create/    → 创建
         GET    /api/library/folders/           → 列出
         PATCH  /api/library/folders/<id>/      → 重命名
         DELETE /api/library/folders/<id>/delete/ → 删除
```

### list_sources 6 种过滤

```
GET /api/library/sources/?ownerId=&courseId=&tags=a,b&status=active&q=组成原理&folderId=
```

| 参数 | 说明 |
|---|---|
| ownerId | 所有者过滤 |
| courseId | 课程关联过滤 |
| tags | 标签交集过滤 |
| status | active/archived |
| q | 标题模糊搜索 (icontains) |
| folderId | 文件夹过滤 |

### 模型变更

- `Source.tags` JSONField — 自由标签列表
- `Source.folder` FK → LibraryFolder — 文件夹关联
- `LibraryFolder` 新建 — 多级嵌套文件夹

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/knowledge/models.py` | Source 加 tags/folder；LibraryFolder 新建 |
| `mentora/knowledge/views.py` | 15 端点 + 全量 Swagger 标注 |
| `config/urls.py` | 路由注册 |
| `knowledge/migrations/0003-0004` | 2 个迁移 |

---

## Topics 模块（T1-T3）

### T1：ORM 模型

| 模型 | 说明 |
|---|---|
| `Topic` | 知识主题节点（多级树，parent FK 自引用） |
| `TopicEdge` | 前置关系（requires/suggests，唯一约束） |
| `TopicEvidence` | 主题↔证据关联（evidence_unit_id + relevance，唯一约束） |

### T2：领域服务

| 函数 | 说明 |
|---|---|
| `build_topic_tree()` | 从结构化数据创建主题树（两遍：Topic → parent） |
| `get_topic_tree()` | 返回嵌套树结构 |
| `link_evidence()` | 批量关联证据（幂等） |

### T3：API（6 端点）

```
POST   /api/courses/<id>/topics/create/  → 创建主题树
GET    /api/courses/<id>/topics/         → 获取主题树
PATCH  /api/topics/<id>/                 → 编辑主题
DELETE /api/topics/<id>/delete/          → 删除主题
POST   /api/topics/<id>/edges/           → 添加前置关系
POST   /api/topics/<id>/evidence/        → 关联证据
```

### 自动标注：LLM 在 Plan 生成时同步标注

`PlanResponse` 扩展 `topics` 字段——PlannerAgent 生成方案时同步输出主题→证据映射：

```json
{
  "topics": [
    {"name": "Cache 原理", "evidence_ids": ["eid-7", "eid-12"]},
    {"name": "虚拟内存", "evidence_ids": ["eid-15"]}
  ]
}
```

`_plan_generate` 中自动调用 `build_topic_tree()` + `link_evidence()`，零额外 API 调用。

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/topics/models.py`（新建） | 3 个 ORM model |
| `mentora/topics/services.py`（新建） | 3 个服务函数 |
| `mentora/topics/views.py`（新建） | 6 个端点 + Swagger 标注 |
| `mentora/topics/apps.py`（新建） | AppConfig |
| `topics/migrations/0001_initial.py` | 建表迁移 |
| `mentora/courses/schemas.py` | PlanResponse 加 topics |
| `mentora/courses/views.py` | _plan_generate 加自动标注 |
| `config/settings.py` | INSTALLED_APPS 加 mentora.topics |
| `config/urls.py` | 6 条 topics 路由 |
