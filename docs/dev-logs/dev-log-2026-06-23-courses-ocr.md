# Courses 模块 + OCR 模块开发记录

- 日期：2026-06-23
- 关联架构：`docs/architecture/agent-runtime-design.md`
- 关联计划：`docs/architecture/end-to-end-implementation-plan.md`

## Courses 模块（C1-C6）

### C1：Course + ProfileRevision + ScopeRevision + ScopeBinding ORM

新增 4 表，补齐建课确认后的正式课程数据结构：

| 表 | 说明 |
|---|---|
| `courses_course` | 课程实体，关联 session + active profile/scope 指针 |
| `courses_profile_revision` | 版本化画像（goal/level/pace/topics/status），不可变草稿→确认→激活 |
| `courses_scope_revision` | 版本化知识作用域 |
| `courses_scope_binding` | 每份资料一条绑定，标记 primary/reference/exam_scope/exercise |

文件：`mentora/courses/models.py`（更新）、`migrations/0003_*`

### C2：领域服务

`mentora/courses/services/__init__.py`（新建）：

| 函数 | 说明 |
|---|---|
| `confirm_course_from_session()` | session → Course + Profile + Scope + Bindings 原子创建 |
| `extend_scope()` | 克隆 scope revision + 追加绑定 + 原子切换 |
| `get_course_scope()` | 返回当前 source_version_ids 列表 |
| `activate_course()` | profile + plan 原子激活 |
| `revise_profile()` | 克隆 profile revision → draft → 等确认 → activate |

### C3：作用域自动注入检索

- `ToolContext` 加 `course_id` 字段
- `RetrieveEvidenceTool` 自动从 `ctx.course_id` 解析作用域传给 `search()`

### C4：QueryCourseScopeTool 对接正式数据

双模式查询：
- `course_id` → Course → ProfileRevision + ScopeBinding（正式数据）
- `course_session_id` → Session.extra（建课未确认，回退）

### C5：revise_profile

画像修订克隆——继承旧值 + 覆盖新字段 → 用户确认 → 原子激活。

### C6：views 对接 API

5 个新端点：

| 端点 | 说明 |
|---|---|
| `POST /api/courses/confirm/` | 建课确认 |
| `GET /api/courses/<id>/` | 课程详情 |
| `PATCH /api/courses/<id>/profile/` | 修订画像 |
| `POST /api/courses/<id>/scope/` | 扩展资料范围 |
| `POST /api/courses/<id>/activate/` | 激活课程 |

---

## OCR 模块（O1-O3）

### O1：Tesseract OCR 适配器

`mentora/parsing/adapters/ocr.py`（新建）：

| 组件 | 说明 |
|---|---|
| `TesseractOCRAdapter` | PyMuPDF 渲染 → PIL → pytesseract → 文本 |
| `is_available()` | 检测 tesseract CLI 是否可用 |
| `ocr_page(page)` | 单页 OCR，150 DPI，chi_sim+eng |

纯图片 PDF 不再抛 `ImageOnlyPDFError`，降级为 OCR 文本。

### O2：图片提取 + EvidenceUnit 生成

- pymupdf: `_find_image_xref()` 匹配图片块 → xref 号存入 `ParsedElement.extra`
- evidence: IMAGE 元素不再跳过，生成 `structure_type="image"` EvidenceUnit
- schemas: `ParsedElement.extra`、`EvidenceUnit.structure_type`、`EvidenceUnit.artifact_ref`

### O3：图片上传 + 多模态描述接入管线

`_extract_and_upload_images()`：
1. `doc.extract_image(xref)` → 图片字节
2. `storage.put_object()` → MinIO
3. `multimodal_provider.image_to_text()` → 文本描述
4. `elem.text` 从 `[图片]` 替换为真实描述 → 可被检索

### 多模态 Provider 预留

`mentora/retrieval/multimodal_provider.py`（新建）：

| 能力 | API | 用途 |
|---|---|---|
| `image_to_text(image_bytes)` | Doubao Vision Pro | 图片 → 文字描述 |
| `multimodal_embed(inputs)` | doubao-embedding-vision | 图文联合向量 |

### ORM 补齐

- `EvidenceUnit.artifact_ref` 字段（migration 0008）
- `persist_evidence.py` 存储 `artifact_ref`

### 完整管线

```
parse(PDF)
  ├─ 文本 → PyMuPDF 文本提取
  ├─ 纯图页 → Tesseract OCR
  └─ 图片块 → extract_image(xref)
                ├─ MinIO 上传 → artifact_ref 落库
                └─ Doubao Vision → 文本描述 → content 可检索
```

---

## 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/courses/models.py` | 新增 Course/ProfileRevision/ScopeRevision/ScopeBinding (4 model) |
| `mentora/courses/services/__init__.py`（新建） | 5 service 函数 |
| `mentora/courses/views.py` | 新增 5 个 Course 管理端点 |
| `config/urls.py` | 新增 5 条 courses URL |
| `mentora/agent_runtime/schemas/context.py` | ToolContext 加 course_id |
| `mentora/agent_runtime/tools/knowledge_tools.py` | 自动解析作用域 |
| `mentora/agent_runtime/tools/course_tools.py` | 双模式查询 |
| `mentora/parsing/adapters/ocr.py`（新建） | TesseractOCRAdapter |
| `mentora/parsing/adapters/pymupdf.py` | 图片 xref 匹配 + OCR 回退 |
| `mentora/parsing/schemas.py` | ParsedElement.extra + EvidenceUnit 结构类型字段 |
| `mentora/parsing/evidence.py` | IMAGE 不跳过，传 artifact_ref |
| `mentora/knowledge/services/persist_evidence.py` | 存 artifact_ref |
| `mentora/knowledge/services/processing.py` | _extract_and_upload_images + 多模态 |
| `mentora/retrieval/models.py` | EvidenceUnit 加 artifact_ref |
| `mentora/retrieval/multimodal_provider.py`（新建） | Doubao Multimodal Provider |
| `config/settings.py` | MULTIMODAL_* + EMBEDDING_* + RERANKER_* 配置 |
