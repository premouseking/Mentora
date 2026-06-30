# 模块边界修复 + 画像草稿流程开发记录

- 日期：2026-06-23
- 关联：`docs/architecture/module-boundaries.md` 审计结果

## Courses C7-C10

### C7：画像候选项生成

`POST /api/courses/sessions/<id>/candidates/`
- Clarifier 分析 inquiry_history → 2-4 个差异化画像方案
- Schema: `ProfileCandidate` + `ProfileCandidatesResponse`

### C8：资料上传触发重规划

`GET /api/courses/<id>/scope-suggest/`
- 检测新解析完成的 SourceVersion → 对比当前作用域
- `suggest_scope_updates()` 服务函数

### C9：课程列表

`GET /api/courses/`
- 按创建时间倒序列出课程

### C10：候选确认生成计划

`POST /api/courses/sessions/<id>/apply-candidate/`
- 选择画像候选 → 创建 `Course + ProfileRevision(draft)`
- 不自动生成计划——用户可编辑 draft 后再确认

## 画像草稿编辑流程（修订）

```
candidates → apply_candidate → Course + ProfileRevision(draft)
  → PATCH /api/courses/<id>/profile/  (编辑草稿)
  → POST /api/courses/<id>/activate/  (确认 → plan_generate → active)
```

符合设计：confirmed 画像不可修改，修改必须克隆为新草稿。

## 模块边界修复（4 项审计）

| # | 问题 | 修复 |
|---|---|---|
| 1 | AssessorAgent 缺少 retrieve_evidence 角色 | `runtime.py` agent_roles 加 "assessor" |
| 2 | source_version_ids 前端可绕过 | `retrieval/views.py` 改为读 course_id → courses services |
| 3 | courses/services 直查 knowledge ORM | 新增 `knowledge/services.get_completed_source_versions()` |
| 4 | persist_evidence 直写 retrieval ORM | 新增 `retrieval/repository.replace_evidence_for_version()` |

## OCR 模块补齐

- `EvidenceUnit.artifact_ref` + `structure_type` 字段落库
- 多模态 `image_to_text()` 接入 `_extract_and_upload_images()`
- IMAGE 证据从 `[图片]` 占位 → 真实描述 → 可检索

## 文件变更汇总

| 文件 | 说明 |
|---|---|
| `mentora/courses/schemas.py` | ProfileCandidate + ProfileCandidatesResponse |
| `mentora/courses/views.py` | C7-C10 端点 + apply_candidate 修订 + activate 集成 plan_generate |
| `mentora/courses/services/__init__.py` | suggest_scope_updates + get_course_info |
| `config/urls.py` | 新增 4 条 routes |
| `mentora/agent_runtime/runtime.py` | agent_roles 补 assessor |
| `mentora/retrieval/views.py` | search_view 服务端校验作用域 |
| `mentora/knowledge/services/__init__.py` | get_completed_source_versions |
| `mentora/retrieval/repository.py` | replace_evidence_for_version |
| `mentora/knowledge/services/persist_evidence.py` | 改调 retrieval 服务 |
| `mentora/assessment/services/__init__.py` | get_latest_session_for_unit |
| `mentora/learning/services/__init__.py` | get_progress 改调 assessment 服务 |
| `mentora/agent_runtime/tools/course_tools.py` | 改调 courses/services |
