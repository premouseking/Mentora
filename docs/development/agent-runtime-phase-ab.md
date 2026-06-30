# Mentora 开发进度

> 更新日期：2026-06-30  
> 分支：`lh`  

---

## 后端 agent_runtime（Phase A-D）

```
Phase A ████████████████████████ 100%  Swagger 标注 + 审计查询 API + 路由独立化
Phase B ████████████████████████ 100%  Pipeline HTTP/SSE 端点 + 引文提取修复
Phase C ████████████████████████ 100%  workflow_runtime 持久化状态机模块
Phase D ████████████████████████ 100%  Redis 滑动窗口限流 + 核心测试（9/9 通过）
```

详见 `docs/development/agent-runtime-phase-ab.md` 的早期版本（Phase C/D 章节）。

---

## 后端 API 补齐（Phase G）

为前端清除硬编码数据而新建的 4 个端点：

| 端点 | 用途 | 文件 |
|------|------|------|
| `GET /api/courses/{id}/phases/` | 课程阶段列表 + 调整影响 | `courses/views.py` |
| `GET /api/courses/{id}/files/` | 课程文件树（按阶段分组） | `courses/views.py` |
| `GET /api/learning/mistakes/` | 错题汇总 | `learning/views.py` + `services/mistakes.py` |
| `GET /api/learning/explanations/` | AI 讲解列表 | `learning/views.py` + `services/mistakes.py` |

---

## 前端适配（Phase F + H）

### F1 — 统一 API 客户端 + HTTP 认证
- 新建 `services/client.ts`（`apiClient` + `tokenStore` + 自动 401 refresh）
- 新建 `services/authApi.ts`（7 个认证端点）
- 改造 `hooks/useAuth.ts`（浏览器模式走 HTTP JWT，dev bypass 保留）
- 改造 `courseApi.ts` / `assessmentApi.ts` 使用 `apiClient`

### F2 — 建课流程对接
- `SetupContinuationPages.tsx` 删 `MOCK_PLAN`/`MOCK_PROFILE`/`MOCK_PHASE_POOL`
- 对接 `getActivePlan()` / `startCourse()` API
- 删除 `VITE_SKIP_BACKEND` 逻辑
- `CoursesPage.tsx` 删除 mock course 逻辑

### F3 — 学习页面对接
- 新建 `services/learningApi.ts`（ContentBlock 类型 + `fetchTask` + `fetchHistory`）
- `LearningTaskPage.tsx` 按 `content_blocks[]` 动态渲染
- `HistoryPage.tsx` 对接 `GET /api/history/`，删 `initialTasks`
- `StageSummaryPage.tsx` 删 `stageEvidence` 硬编码

### F4 — 资料库同步
- `documentApi.ts` 新增 `fetchFolders`/`createFolder`/`deleteFolder`/`moveSource`/`fetchTags`
- `renameFolder` / `updateSourceTags` 预留（待前端 UI）
- `LibraryPage.tsx` 文件夹/拖拽移动/标签全对接 API

### H1-H5 — 硬编码清理
- 新增前端 API 函数对接 4 个 G 阶段端点
- `CourseWorkspacePage` / `FileExplorer` / `MistakeReviewPanel` 替换硬编码导入
- 删除 `mockCourses.ts`、`courseFiles[]` 数据、无引用的硬编码数组

---

## 文件变更统计

### 后端新增/改造

```
apps/api/
├── config/
│   ├── settings.py           (+CACHES Redis, +workflow_runtime, +task routes)
│   └── urls.py                (+6 条新路由)
├── mentora/
│   ├── agent_runtime/
│   │   ├── views.py           (+pipeline_chat, +pipeline_chat_stream, +run_list, +run_detail)
│   │   ├── urls.py            (新)
│   │   ├── decorators.py      (新 — rate_limit)
│   │   ├── schemas/task.py    (agent_role/user_message 可选)
│   │   └── agents/
│   │       ├── turn_loop.py   (引文修复 — _execute_tool 三元组)
│   │       └── {tutor,planner,assessor}.py  (清理 _extract_citations)
│   ├── workflow_runtime/      (新模块 — 6 文件)
│   ├── courses/
│   │   └── views.py           (+course_phases, +course_files)
│   └── learning/
│       ├── views.py           (+mistake_list, +explanation_list)
│       └── services/
│           └── mistakes.py    (新 — get_mistake_items, get_explanations)
└── tests/
    ├── test_agent_loop.py     (+2 引文测试)
    └── test_rate_limit.py     (新 — 3 限流测试)
```

### 前端新增/改造

```
apps/web/src/
├── services/
│   ├── client.ts              (新 — apiClient + tokenStore)
│   ├── authApi.ts             (新 — 7 认证端点)
│   ├── learningApi.ts         (新 — ContentBlock 类型 + fetchTask/fetchHistory/fetchMistakes/fetchExplanations)
│   ├── courseApi.ts           (改用 apiClient)
│   ├── assessmentApi.ts       (改用 apiClient)
│   └── documentApi.ts         (+folder/tag/move/fetchCourseFiles/fetchCoursePhases)
├── hooks/
│   └── useAuth.ts             (+HTTP JWT 支持)
├── pages/
│   ├── SetupContinuationPages.tsx  (删 MOCK_PLAN → API)
│   ├── CoursesPage.tsx        (删 mock course → API)
│   ├── CourseWorkspacePage.tsx (删 3 处硬编码 → API)
│   ├── LearningTaskPage.tsx   (删硬编码 → content_blocks 动态渲染)
│   ├── HistoryPage.tsx        (接 /api/history/)
│   ├── LibraryPage.tsx        (文件夹/标签/移动 全接 API)
│   └── StageSummaryPage.tsx   (删 stageEvidence)
├── components/
│   ├── FileExplorer.tsx       (类型迁移 → service types)
│   └── MistakeReviewPanel.tsx (类型迁移 → service types)
└── data/
    ├── mockCourses.ts         (已删除)
    ├── history.ts             (删 initialTasks)
    ├── files.ts               (删 courseFiles 数据)
    ├── library.ts             (删 libraryFolders)
    └── courses.ts             (删 stageEvidence)
```

## 下一步

1. **后端**：`TaskContent` 模型 + `GET /api/learning/tasks/{id}/` 端点（支撑 LearningTaskPage 内容渲染）
2. **前端**：文件夹重命名 UI + 标签编辑 UI（API 已就绪）
3. **数据**：`error_reason` AI 错因分析 + `phase.state` 真实进度计算

详见 `docs/development/frontend-reserved-api.md`（交付前端文档）。
