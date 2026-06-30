# 前端待设计 UI 与预留 API 文档

> 交付日期：2026-06-30  
> 目标读者：前端开发人员  
> 后端 API 已全部实现并验证，前端 UI 待设计对接。

---

## 1. 文件夹重命名

### 后端端点

```
PATCH /api/library/folders/{folder_id}/
Content-Type: application/json
```

### 请求体

```json
{
  "name": "新文件夹名称"
}
```

### 响应

```json
{ "id": "uuid", "name": "新文件夹名称" }
```

### 前端现状

`LibraryPage.tsx` 的 `FolderSidebar` 组件中，文件夹列表已通过 `fetchFolders()` 从后端加载。重命名功能的后端函数 `renameFolder(folderId, name)` 已在 `services/documentApi.ts` 中实现。

### 待设计 UI

- **触发方式**：双击文件夹名称、右键菜单「重命名」、或文件夹旁编辑图标
- **编辑态**：内联 `<input>` 替换文件夹名称文字，Enter 确认 / Esc 取消 / 失焦保存
- **对接**：调用 `renameFolder(folderId, newName)` → 成功后更新本地 folders 状态

### 对应文件

- 前端：`pages/LibraryPage.tsx`（`FolderSidebar` 内）
- API：`services/documentApi.ts` — `renameFolder()`

---

## 2. 资料标签编辑

### 后端端点

```
POST /api/library/sources/{source_id}/tags/
Content-Type: application/json
```

### 请求体

```json
{
  "tags": ["计算机组成原理", "Cache", "存储系统"]
}
```

### 响应

```json
{ "status": "ok" }
```

### 现有标签列表

```
GET /api/library/tags/
→ { "tags": ["标签1", "标签2", ...] }
```

### 前端现状

`LibraryPage.tsx` 的详情面板展示 `item.tags` 为只读标签。标签数据通过 `fetchTags()` 获取。`updateSourceTags(sourceId, tags)` 已在 `services/documentApi.ts` 实现。

### 待设计 UI

- **标签展示**：详情面板中每个 tag 旁加 × 删除按钮
- **添加标签**：「+ 添加标签」按钮 → 弹出输入框或下拉选择已有标签
- **自动建议**：输入时从 `fetchTags()` 列表中匹配补全
- **对接**：每次增删标签后调用 `updateSourceTags(sourceId, newTags)` 持久化

### 对应文件

- 前端：`pages/LibraryPage.tsx`（`LibraryDetailPanel` 内）
- API：`services/documentApi.ts` — `fetchTags()` + `updateSourceTags()`

---

## 3. 学习任务内容页

### 后端端点

```
GET /api/learning/tasks/{task_id}/
```

### 响应结构（LearningTaskDetail）

```typescript
interface LearningTaskDetail {
  task_id: string;
  title: string;            // "Cache 映射方式与命中率"
  task_type: string;        // "lecture" | "exercise" | "project" | "review"
  unit_title: string;       // "存储系统"
  phase_title: string;      // "重点突破"
  position: number;
  estimated_minutes: number;
  content_blocks: ContentBlock[];  // 按序渲染的内容块
  sources: TaskSource[];
}

type ContentBlock =
  | { type: "heading";  id: string; label: string; level: 2 | 3 }
  | { type: "paragraph"; id: string; text: string; modes?: { simple?: string; example?: string; standard: string } }
  | { type: "citation"; id: string; source_title: string; chapter: string; page_number: number; evidence_id: string }
  | { type: "diagram";  id: string; label: string; diagram_type: string; data: object }
  | { type: "callout";  id: string; variant: "tip" | "warning" | "info"; text: string }
  | { type: "quiz";     id: string; question: string; options: string[]; correct_index: number; explanation: string; next_step_link?: string }
```

### 前端现状

`LearningTaskPage.tsx` 已完成完整重构——删除了全部硬编码内容，改为从 API 加载后按 `content_blocks` 数组动态渲染。每种 block 类型有对应的渲染组件（`BlockHeading` / `BlockParagraph` / `BlockCitation` / `BlockQuiz` 等）。

### 待后端实现

**后端 TaskContent 模型尚未创建。** 需要：

1. 在 `learning/models.py` 中扩展 `LearningPlanTaskTemplate` 或新建 `TaskContent` 模型，添加 `content_json: JSONField` 存储 `ContentBlock[]`
2. 实现 `GET /api/learning/tasks/{task_id}/` 端点，从模型读取 content_blocks 返回
3. 规划：PlannerAgent 生成计划时填充 content_blocks（含段落、题目、引用等）

### 对应文件

- 前端：`pages/LearningTaskPage.tsx` + `services/learningApi.ts`（已就绪，等待后端 endpoint 有数据）
- 后端：`learning/models.py` + `learning/views.py`（待开发）

---

## 4. 错误原因自动分析（预留）

### 后端现状

`GET /api/learning/mistakes/` 已返回 `error_reason` 字段，当前为空字符串 `""`。

### 前端现状

`MistakeReviewPanel.tsx` 已读取 `error_reason` 字段展示。

### 待实现

后端在 `POST /api/assessment/.../attempts/` 提交作答后，异步调用 agent_runtime 分析错因，写入 `error_reason` 字段。

---

## 5. 阶段进度（phases state）

### 后端现状

`GET /api/courses/{id}/phases/` 返回 `state` 字段，当前降级策略：position=0 → `completed`，最后一个 → `active`，其余 → `upcoming`。

### 待实现

接入 `LearningSession` 模型，根据实际完成情况计算每个 phase 的真实 state。

---

## API 函数速查表

| 函数 | 端点 | 状态 |
|------|------|------|
| `renameFolder(id, name)` | `PATCH /api/library/folders/{id}/` | 后端已就绪，前端待 UI |
| `updateSourceTags(id, tags)` | `POST /api/library/sources/{id}/tags/` | 后端已就绪，前端待 UI |
| `fetchTask(taskId)` | `GET /api/learning/tasks/{id}/` | 后端待实现 TaskContent 模型 |
| `fetchMistakes(courseId)` | `GET /api/learning/mistakes/` | 已对接，error_reason 待填充 |
| `fetchExplanations(courseId)` | `GET /api/learning/explanations/` | 已对接 |
| `fetchCoursePhases(courseId)` | `GET /api/courses/{id}/phases/` | 已对接，state 精度待提升 |
| `fetchCourseFiles(courseId)` | `GET /api/courses/{id}/files/` | 已对接 |
