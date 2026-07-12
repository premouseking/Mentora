# 课程对话 API 需求规格

> 版本：v1 | 日期：2026-06-30 | 用途：后端开发讨论用
>
> 本文档列出课程对话功能所需的所有后端改动，区分「修改现有 API」和「新增 API」。不涉及前端细节。

---

## 一、总览

| 分类 | 数量 | 说明 |
|------|------|------|
| 修改现有接口 | 1 | `POST /api/chat/stream/` 增强 |
| 新增接口 | 6 | 会话 CRUD + 消息查询 |
| 纯后端逻辑（无新接口） | 4 | 上下文注入、历史利用、引用提取、进度感知 |
| 数据模型 | 2 | ChatSession + ChatMessage |

---

## 二、修改现有接口

### 2.1 POST /api/chat/stream/（增强）

**当前行为**：接收 `{ message, history }`，但实际只用了 `message`。`context_sources` 硬编码为空，`history` 被忽略。`course_id` 不接收。

**需要改为**：

| 项目 | 当前 | 改为 |
|------|------|------|
| 接收 `course_id` | 无 | 必填，UUID |
| 接收 `history` | 有但未使用 | 有，读取后填入 `OrchestratorTask.history_messages` |
| `context_sources` | 硬编码 `[]` | 根据 `course_id` 查激活作用域，填入资料版本 ID 列表 |
| 系统提示词 | 无课程信息 | 注入课程名称、目标、可用资料列表等模板变量 |
| 消息持久化 | 无 | 运行完成后，将 user 消息和 assistant 回复写入 ChatMessage 表 |
| `session_id` | 无 | 可选，不传则自动创建新 ChatSession |

**请求体**：

```jsonc
{
  "message": "什么是冯·诺依曼结构？",          // 必填
  "course_id": "550e8400-...",                  // 必填（新增）
  "session_id": "660e8400-...",                 // 可选（新增），不传则自动创建新会话
  "history": [                                   // 已有，现在需要后端实际使用
    { "role": "user", "content": "上一条" },
    { "role": "assistant", "content": "上一条回复" }
  ]
}
```

**响应（SSE 事件流）**：不变，沿用现有事件类型 `agent.run.started` / `agent.thinking` / `agent.tool.call` / `agent.tool.result` / `agent.response` / `agent.run.completed` / `agent.run.error`。

**后端处理流程（增强后）**：

```
1. 校验 message、course_id
2. 根据 course_id 查询 Course 基础信息（名称、目标）
3. 根据 course_id 查询激活的 KnowledgeScopeRevision → 获取 source_version_ids
4. 构造 OrchestratorTask：
   - context_sources = source_version_ids
   - history_messages = 解析请求中的 history
   - 系统提示词注入 {course_name} {source_titles} 等变量
5. orchestrator.run_stream(task) 执行
6. 运行完成后：
   - 如果请求未传 session_id → 创建新 ChatSession
   - 保存 user 消息（role=user）
   - 保存 assistant 消息（role=assistant，含 citations、usage、orchestrator_run_id）
   - 在 agent.run.completed 事件中附带 session_id 和 message_id
```

---

## 三、新增接口

### 3.1 GET /api/courses/{course_id}/chat-sessions/

获取某个课程下的所有聊天会话列表。

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径参数 | `course_id` (UUID) |
| 权限 | 当前用户必须是课程所有者 |
| 排序 | 按 `updated_at` 倒序（最近活跃的在前） |

**响应**：

```json
{
  "sessions": [
    {
      "id": "660e8400-...",
      "name": "第三章课后疑问",
      "message_count": 12,
      "created_at": "2026-06-28T10:00:00Z",
      "updated_at": "2026-06-30T09:30:00Z"
    }
  ]
}
```

---

### 3.2 POST /api/courses/{course_id}/chat-sessions/

为课程创建新的空会话。

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径参数 | `course_id` (UUID) |
| 请求体 | `{ "name": "考前集中答疑" }`（可选，默认"新对话"） |
| 权限 | 当前用户必须是课程所有者 |

**响应**：

```json
{
  "id": "770e8400-...",
  "name": "考前集中答疑",
  "message_count": 0,
  "created_at": "2026-06-30T10:00:00Z",
  "updated_at": "2026-06-30T10:00:00Z"
}
```

---

### 3.3 GET /api/chat-sessions/{session_id}/

获取单个会话详情。

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径参数 | `session_id` (UUID) |
| 权限 | 当前用户必须拥有该会话所属课程 |

**响应**：同 3.2 的响应结构。

---

### 3.4 PATCH /api/chat-sessions/{session_id}/

更新会话属性（重命名）。

| 项目 | 值 |
|------|-----|
| 方法 | PATCH |
| 路径参数 | `session_id` (UUID) |
| 请求体 | `{ "name": "新名称" }` |
| 权限 | 当前用户必须拥有该会话所属课程 |

**响应**：同 3.2 的响应结构。

---

### 3.5 DELETE /api/chat-sessions/{session_id}/

删除会话及其所有消息。

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径参数 | `session_id` (UUID) |
| 权限 | 当前用户必须拥有该会话所属课程 |
| 级联 | 删除会话时级联删除所有 ChatMessage |

**响应**：`204 No Content`

---

### 3.6 GET /api/chat-sessions/{session_id}/messages/

获取某个会话的历史消息列表。

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径参数 | `session_id` (UUID) |
| 权限 | 当前用户必须拥有该会话所属课程 |
| 排序 | 按 `created_at` 正序（旧→新） |
| 分页 | 建议支持 `?limit=50&offset=0`，不传则全量返回 |

**响应**：

```json
{
  "messages": [
    {
      "id": "880e8400-...",
      "session_id": "770e8400-...",
      "role": "user",
      "content": "什么是冯·诺依曼结构？",
      "created_at": "2026-06-30T09:29:00Z"
    },
    {
      "id": "990e8400-...",
      "session_id": "770e8400-...",
      "role": "assistant",
      "content": "冯·诺依曼结构由五大部分组成：运算器、控制器……",
      "citations": [
        {
          "source_title": "计组教材.pdf",
          "page_number": 23,
          "content": "冯·诺依曼结构由运算器、控制器、存储器、输入设备和输出设备组成……",
          "content_preview": "冯·诺依曼结构由运算器、控制器、存储器、输入设备和输出设备组成……"
        }
      ],
      "tool_calls_made": [
        { "tool_name": "retrieve_evidence", "args": { "query": "冯·诺依曼结构" } }
      ],
      "usage": { "prompt_tokens": 1200, "completion_tokens": 300 },
      "orchestrator_run_id": "chat-a1b2c3d4e5f6",
      "status": "completed",
      "created_at": "2026-06-30T09:29:15Z"
    }
  ],
  "total": 2
}
```

---

## 四、数据模型（新增）

### 4.1 ChatSession

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | UUID | PK | 主键 |
| `course` | FK → Course | NOT NULL, CASCADE | 所属课程 |
| `user` | FK → User | NOT NULL, CASCADE | 冗余，方便按用户查询（等于 course.user） |
| `name` | varchar(200) | NOT NULL, default="新对话" | 会话名称 |
| `message_count` | int | NOT NULL, default=0 | 消息数量（反范式，便于列表展示） |
| `created_at` | datetime | auto_now_add | 创建时间 |
| `updated_at` | datetime | auto_now | 最后活跃时间 |

**索引**：`(course, created_at)`、`(user, updated_at)`

### 4.2 ChatMessage

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | UUID | PK | 主键 |
| `session` | FK → ChatSession | NOT NULL, CASCADE | 所属会话 |
| `role` | varchar(16) | NOT NULL | user / assistant |
| `content` | text | NOT NULL | 消息文本 |
| `citations_json` | JSON | nullable | 引用列表（仅 assistant） |
| `tool_calls_json` | JSON | nullable | 工具调用记录（仅 assistant） |
| `usage_json` | JSON | nullable | Token 用量（仅 assistant） |
| `orchestrator_run_id` | varchar(64) | nullable | 关联 agent_runtime 审计记录 |
| `status` | varchar(16) | default="completed" | completed / aborted（仅 assistant） |
| `created_at` | datetime | auto_now_add | 创建时间 |

**索引**：`(session, created_at)`

### 4.3 与其他模型的关系

```
User ─── Course ─── ChatSession ─── ChatMessage
                                   │
                                   │ orchestator_run_id
                                   ↓
                          agent_runtime.OrchestratorRun
```

- `ChatSession.user` 冗余自 `course.user`，便于跨课程的用户维度查询。
- `ChatMessage.orchestrator_run_id` 指向 `agent_runtime.OrchestratorRun`，用于追溯每次回答的技术执行轨迹。

---

## 五、纯后端逻辑改动（不涉及新 API）

### 5.1 课程上下文注入

| 改动位置 | 内容 |
|----------|------|
| `agent_runtime/views.py` | `chat_stream` 和 `chat_api` 中从请求体读取 `course_id` |
| 同上 | 根据 `course_id` 查 `Course` 基础信息 + `active_knowledge_scope_revision` |
| 同上 | 将资料版本 ID 填入 `OrchestratorTask.context_sources` |
| `agent_runtime/prompts/templates/tutor.json` | 系统提示词增加 `{course_name}` `{source_titles}` 等模板变量 |

### 5.2 历史消息后端利用

| 改动位置 | 内容 |
|----------|------|
| `agent_runtime/views.py` | `chat_stream` 和 `chat_api` 中解析请求体 `history` 字段 |
| 同上 | 将历史消息列表填入 `OrchestratorTask.history_messages` |
| `agent_runtime/context/` | 当前的 `ContextManager` 已有 `_build_message_context()`，传入后自然进入上下文裁剪逻辑 |

**注意**：如果后续会话持久化后，后端可直接从 `ChatMessage` 表读取历史，不一定依赖前端每次都传 `history`。但过渡阶段两者并存：前端传的 `history` 用于即时上下文，持久化的消息用于恢复。

### 5.3 引用提取完成

| 改动位置 | 内容 |
|----------|------|
| `agent_runtime/agents/tutor.py`（或对应文件） | 完善 `_extract_citations` 函数 |
| 同上 | 从 `retrieve_evidence` 工具返回结果中提取 `SearchResult` 列表 |
| 同上 | 填入用户可见 `AgentOutput.citations`，包含：source_title、page_number、content、content_preview；不向前端暴露 evidence_id |

### 5.4 学习进度感知

| 改动位置 | 内容 |
|----------|------|
| `agent_runtime/prompts/templates/tutor.json` | 提示词中增加：当用户问到自己掌握情况/进度/薄弱点时应调用进度查询工具 |
| `agent_runtime/agents/tutor.py` | 在 `tool_names` 中加入 `query_knowledge_scope` 和 `query_learning_progress` |
| `agent_runtime/tools/knowledge_tools.py` | 确认两个工具能根据 `course_id` 正确返回数据（当前可能是占位实现） |

### 5.5 多课程并发隔离（P2）

| 改动位置 | 内容 |
|----------|------|
| `agent_runtime/views.py` | 取消模块级 `_orchestrator` 全局单例 |
| 同上 | 每次请求按需创建 Orchestrator 实例（`ModelGateway` 和 `PromptManager` 可保持单例） |

---

## 六、汇总对比

### 前后对比

| 维度 | 当前 | 目标 |
|------|------|------|
| 模型层 | 无对话持久化 | ChatSession + ChatMessage |
| 会话管理 | 无 | 创建/列表/重命名/删除 |
| 历史恢复 | 刷新丢失 | 进入课程自动加载 |
| 上下文 | 通用辅导（无课程信息） | 绑定课程，注入资料作用域 |
| 多轮对话 | 前端传 history 但后端忽略 | 后端实际利用 history |
| 引用 | 占位，返回空列表 | 完整提取 citations |
| 进度感知 | 工具有但 Agent 不用 | Agent 主动调用进度工具 |

### 接口数量汇总

| 分类 | 端点 | 方法 | 状态 |
|------|------|------|------|
| 流式对话 | `/api/chat/stream/` | POST | **修改** |
| 会话列表 | `/api/courses/{course_id}/chat-sessions/` | GET | **新增** |
| 创建会话 | `/api/courses/{course_id}/chat-sessions/` | POST | **新增** |
| 会话详情 | `/api/chat-sessions/{session_id}/` | GET | **新增** |
| 更新会话 | `/api/chat-sessions/{session_id}/` | PATCH | **新增** |
| 删除会话 | `/api/chat-sessions/{session_id}/` | DELETE | **新增** |
| 消息列表 | `/api/chat-sessions/{session_id}/messages/` | GET | **新增** |

---

## 七、待讨论事项

以下点在动手编码前建议和后端开发人员对齐：

1. **ChatSession.user 冗余**：是否需要在 `ChatSession` 上存 `user`？存了方便跨课程查询，但多了一个需要保持一致的字段。如果不存，权限校验走 `session.course.user`。

2. **消息持久化时机**：是在 Orchestrator 运行完成后由视图层写入，还是让 Orchestrator 内部通过回调写入？建议前者，保持 Agent 无状态。

3. **分页**：`GET /messages/` 是否必须分页？初期消息量不大，可以先全量返回，后续加上 `limit/offset`。

4. **是否保留非流式 `/api/chat/`**：当前有一个非流式版本，是否也需要加上 `course_id` 和持久化？建议同步增强，保持一致性。

5. **`history` 字段定位**：持久化完成后，前端是否还需要传 `history`？建议过渡期两者并存（前端传 history 用于即时上下文，后端也从 DB 取），最终以后端 DB 为准。

---

> @see docs/core-features/course-conversation-requirements.md  
> @see docs/architecture/agent-runtime-design.md  
> @see docs/architecture/end-to-end-implementation-plan.md
