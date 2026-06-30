# 课程对话功能需求

> 版本：v1 | 日期：2026-06-30 | 状态：需求整理中
>
> 本文档定义「课程对话」（Course Conversation）的完整功能需求。与建课流程中的「结构化追问」（问题卡式澄清）不同，课程对话面向的是课程已激活后的**自由问答场景**——学生就课程内容向 AI 提问，AI 基于课程资料给出有引用来源的回答。

---

## 一、功能定位

### 1.1 与通用聊天的区别

Mentora 不是通用聊天机器人（参见 `docs/architecture/end-to-end-implementation-plan.md` §1）。课程对话有以下硬约束：

- **绑定具体课程**：每轮对话都在一个已激活课程的上下文中发生。
- **知识作用域受限**：AI 只能检索当前课程激活的 `CourseKnowledgeScopeRevision` 中的资料，不能访问用户整个资源库，更不能做开放网络搜索。
- **回答必须有引用**：每句基于资料的结论必须标注来源（资料名、页码、坐标等）。
- **不替代教学逻辑**：对话是补充性问答，不驱动学习计划、不修改掌握度。

### 1.2 在整体产品中的位置

从端到端方案 §2.4 的产品面板定义来看：

```
继续学习 ─── 推荐下一任务
学习     ─── 当前学习包（讲解 + 练习）
提问     ─── 课程问答 ← 本文档覆盖
练习     ─── 自测和错题
知识地图 ─── 主题图谱
课程资料 ─── 作用域管理
```

课程对话即是面板中的「提问」，在整个学习闭环中扮演**基于资料的即时答疑**角色。

### 1.3 与建课追问的区分

| 维度 | 建课追问 | 课程对话 |
|------|---------|---------|
| 时机 | 课程未生成时 | 课程已激活后 |
| 目的 | 收集画像信息，生成方案 | 解答学习疑问 |
| 形式 | 结构化问题卡（1-3 选项） | 自由文本输入 + 流式输出 |
| 工具 | 字段提取 + 配置面板填充 | 资料检索 + 学习进度查询 |
| 通信 | 同步请求-响应 | SSE 流式 |

---

## 二、用户交互模式

### 2.1 基本流程

```
课程工作台 → 点击「提问」标签页
  → 显示对话面板（历史消息 + 输入框）
  → 用户输入问题并发送
  → 流式显示 AI 思考过程和最终回答
  → 回答中标注引用来源（可点击跳转原文）
  → 对话记录自动保存，切换页面不丢失
```

### 2.2 前端交互要求

- **输入方式**：文本输入框 + 发送按钮，支持 Enter 发送。
- **展示方式**：气泡式对话列表，用户消息右对齐、AI 回答左对齐。
- **流式效果**：AI 回答逐字/逐块出现（SSE 驱动的打字机效果）。
- **引用展示**：回答底部列出引用的资料来源，点击可跳转到原文位置（PDF 页码、PPT 幻灯片等）。
- **思考过程**：AI 调用资料检索等工具时，界面可显示"正在检索…"等中间状态（对应 SSE 事件 `agent.tool.call` / `agent.tool.result`）。
- **历史恢复**：进入课程时自动加载该课程的对话历史。

### 2.3 对话管理

- **一个课程可以有多个会话**：例如"第三章课后疑问"和"考前集中答疑"是不同的会话。
- **会话可命名、可删除**。
- **当前激活会话**：同一时间只能有一个活跃对话流，但用户可切换查看历史会话。

---

## 三、功能需求详情（按优先级）

### 3.1 P0：课程上下文注入

**当前状态**：视图代码在构建 `OrchestratorTask` 时 `context_sources` 始终传空列表，`course_id` 完全没有接收。

**需求描述**：

后端视图需要从请求中接收 `course_id`，然后：
1. 查询当前课程激活的 `CourseKnowledgeScopeRevision`，获取可用资料版本列表。
2. 获取课程基础信息（名称、目标等），填入 Agent 系统提示词的模板变量（如 `course_name`、`source_titles`）。
3. 将资料版本 ID 列表填入 `context_sources`，用于 `retrieve_evidence` 工具做作用域过滤。

**接口变更**：请求体新增 `course_id` 字段（必填）。

### 3.2 P0：历史消息在后端的实际利用

**当前状态**：前端发送请求时已携带 `history` 字段，但后端视图代码完全忽略了请求体中的 `history`。

**需求描述**：

1. 后端从请求体读取 `history` 字段，解析为消息列表。
2. 将历史消息传入 `OrchestratorTask.history_messages`。
3. ContextManager 按预算优先级裁剪历史，将最近 N 轮对话纳入上下文。

这样多轮对话才能形成连贯的问答链，而不是每轮退化为独立单轮。

### 3.3 P0：对话历史持久化

**当前状态**：没有对话存储模型。刷新页面后历史丢失。

**需求描述**：

需要新建两个数据模型：

- **ChatSession（对话会话）**：记录一次对话会话的元信息，包括所属课程、创建时间、状态（活跃/已归档）、会话名称。
- **ChatMessage（对话消息）**：记录会话中的每条消息，包括角色（user/assistant）、文本内容、引用的证据列表（`citations`）、工具调用记录（`tool_calls_made`）、Token 用量、关联的 `OrchestratorRun.id`。

**模型设计**见 §五。

### 3.4 P1：引用提取完成

**当前状态**：TutorAgent 和 PlannerAgent 中的引用提取函数（`_extract_citations`）直接返回空列表。虽然工具调用循环中能正确从 `retrieve_evidence` 返回结果中获得引用信息，但这些信息没有被填入最终的 `AgentOutput.citations`。

**需求描述**：

1. 完善 `_extract_citations` 函数，从 `retrieve_evidence` 工具的返回结果中提取 `SearchResult` 列表。
2. 将引用信息填入 `AgentOutput.citations`，确保包含：证据 ID、资料名称、页码/坐标、内容预览片段。
3. 前端根据 `citations` 字段渲染引用列表，并支持跳转到原文位置。

### 3.5 P1：学习进度感知

**当前状态**：工具层已有 `query_knowledge_scope` 和 `query_learning_progress` 两个工具（在 `knowledge_tools.py` 中），但 TutorAgent 的系统提示词没有引导它使用这些工具，实际对话中不会被触发。

**需求描述**：

1. TutorAgent 的系统提示词模板（`prompts/templates/tutor.json`）中增加提示：当用户的问题涉及自身掌握情况、进度、薄弱点时，应调用进度查询工具。
2. 将 `query_knowledge_scope` 和 `query_learning_progress` 加入 TutorAgent 的 `tool_names`。
3. 确保这两个工具能正确返回当前课程的知识范围（主题、重点、薄弱点）和学习进度（已完成任务、掌握度）。

### 3.6 P2：多课程并发隔离

**当前状态**：视图代码使用模块级全局变量（`_orchestrator`、`_gateway`、`_prompt_manager`）缓存单例实例，所有请求共用一个编排器。

**需求描述**：

1. PromptManager 和管理类实例可以全局共享（无状态），不需要改。
2. Orchestrator 的实例化应该改为按请求创建（或按会话创建），避免不同课程的对话相互干扰。
3. 或者改为按 `course_id` 维护一个实例池，相同的 `course_id` 复用同一个 Orchestrator。

### 3.7 P2：停止生成

**需求描述**：

在流式对话中，用户点击「停止生成」按钮后：
1. 前端关闭 SSE 连接。
2. 后端收到连接断开后，中止 Agent 运行（可通过 Celery 任务撤销实现）。
3. 已生成的部分内容保存到对话历史，标注为「用户中止」。

### 3.8 P2：重新生成

**需求描述**：

对 AI 的某条回答，用户可以点击「重新生成」：
1. 前端发送相同的问题 + 截至该问题之前的历史（不含被替换的回答）。
2. 新回答覆盖旧回答在对话历史中的位置。

---

## 四、接口定义

### 4.1 流式对话 SSE

```
POST /api/chat/stream/
```

已在 `docs/openapi.yaml` 中定义，当前实现可用。需要新增：

**请求体变更**：

```json
{
  "message": "字符串，用户问题（必填）",
  "history": [
    {"role": "user", "content": "上一条消息"},
    {"role": "assistant", "content": "上一条回答", "citations": []}
  ],
  "course_id": "课程 ID（必填，新增）",
  "session_id": "会话 ID（可选，不传则创建新会话）"
}
```

**SSE 事件流**（已有，无需变更）：

| 事件名 | 含义 |
|--------|------|
| `agent.run.started` | 编排器接受任务 |
| `agent.thinking` | 开始新一轮模型调用 |
| `agent.tool.call` | 工具调用开始（如检索资料） |
| `agent.tool.result` | 工具调用完成 |
| `agent.response` | 模型返回文本片段（流式） |
| `agent.run.completed` | 运行完成，含最终回答和引用 |
| `agent.run.error` | 运行失败 |

### 4.2 会话管理接口

这些接口尚未实现，需要新增：

```
GET    /api/courses/{course_id}/sessions/        # 获取课程的会话列表
POST   /api/courses/{course_id}/sessions/        # 创建新会话
GET    /api/sessions/{session_id}/messages/      # 获取会话的历史消息
PATCH  /api/sessions/{session_id}/               # 更新会话名称、归档状态
DELETE /api/sessions/{session_id}/               # 删除会话
```

---

## 五、数据模型

### 5.1 ChatSession（新增）

对应数据库表 `chat_session`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `course_id` | FK → Course | 所属课程 |
| `name` | varchar(200) | 会话名称（默认"新对话"） |
| `message_count` | int | 消息数量（反范式） |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 最后活跃时间 |

### 5.2 ChatMessage（新增）

对应数据库表 `chat_message`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `session_id` | FK → ChatSession | 所属会话 |
| `role` | varchar(16) | user / assistant |
| `content` | text | 消息文本内容 |
| `citations_json` | JSON | 引用的证据列表 |
| `tool_calls_json` | JSON | 工具调用记录（仅 assistant） |
| `usage_json` | JSON | Token 用量（仅 assistant） |
| `orchestrator_run_id` | varchar(64) | 关联的编排运行记录 |
| `status` | varchar(16) | completed / aborted（仅 assistant） |
| `created_at` | datetime | 创建时间 |

### 5.3 与现有审计模型的关系

`ChatMessage.orchestrator_run_id` 指向 `agent_runtime.OrchestratorRun.id`。已有的审计模型（`OrchestratorRun`、`SubAgentRun`、`ToolInvocation`）负责记录技术层面的执行细节；`ChatMessage` 负责存储用户可见层面的消息内容。两者通过 `orchestrator_run_id` 关联，互补不重复。

---

## 六、与现有模块的集成点

### 6.1 与 agent_runtime 的关系

`agent_runtime` 已实现 Phase 1 + Phase 2，以下组件可直接复用：

- **Orchestrator + TutorAgent**：对话响应引擎，流式 SSE 输出已可用。
- **ToolRegistry + retrieve_evidence**：资料检索（当前为占位实现，需对接 retrieval 模块）。
- **ContextManager + TokenCounter**：上下文裁剪，历史消息纳入预算管理。
- **SSE EventEmitter**：流式事件，前端可直接消费现有事件类型。

需要新增/修改的部分：
- 视图层接收 `course_id` 并注入上下文
- 引用提取函数完善
- 检索工具对接真实 retrieval 模块

### 6.2 与 retrieval 模块的关系

`retrieve_evidence` 工具需要调用 `mentora.retrieval.search.search(query, top_k, source_version_ids)`，按课程作用域过滤结果。这是课程对话能「基于资料回答」的核心依赖。

### 6.3 与 courses 模块的关系

需要从 courses 模块获取：
- 课程激活的知识作用域修订（`active_knowledge_scope_revision_id`）
- 课程基础信息（名称、目标等，用于系统提示词渲染）

### 6.4 与 learning 模块的关系

`query_knowledge_scope` 和 `query_learning_progress` 需要调用 learning 模块的服务，获取学生的知识范围和进度。当前这两个工具可能也是占位实现，需要在 P1 阶段确认。

---

## 七、当前实现状态与差距

### 7.1 已完成

| 项 | 状态 | 说明 |
|-----|------|------|
| Agent 运行时骨架 | ✅ | Phase 1，FakeProvider 测试 25/25 通过 |
| 真实 LLM 联调 | ✅ | Phase 2，DeepSeek API + SSE 流式输出 |
| `POST /api/chat/stream/` | ✅ | 流式 SSE 端点可用 |
| 上下文管理框架 | ✅ | ContextManager + TokenCounter + 预算裁剪 |
| 工具机制 | ✅ | ToolRegistry + retrieve_evidence（占位）+ 进度查询工具 |
| 审计模型 | ✅ | OrchestratorRun + SubAgentRun + ToolInvocation |
| 前端基础聊天 UI | ✅ | AppShell 中已有聊天面板 |

### 7.2 待完成（从高到低）

| 项 | 优先级 | 工作量估算 |
|-----|--------|----------|
| 视图层接收 `course_id` + 注入上下文 | P0 | 小（~2h） |
| 视图层利用 `history` 字段 | P0 | 小（~1h） |
| ChatSession + ChatMessage 模型+迁移 | P0 | 中（~4h） |
| 会话管理接口（CRUD） | P0 | 中（~4h） |
| 消息持久化逻辑（写完消息 + 返回 session_id） | P0 | 中（~3h） |
| 引用提取完善 | P1 | 中（~3h） |
| 检索工具对接真实 retrieval | P1 | 中（~4h） |
| 学习进度感知（提示词 + 工具激活） | P1 | 小（~2h） |
| 多课程并发隔离 | P2 | 小（~2h） |
| 停止生成 | P2 | 中（~3h） |
| 重新生成 | P2 | 小（~2h） |

### 7.3 不在此 Phase 的项

- AssessorAgent（测评 Agent）：Phase 3
- 测评结果回写 learning 模块：Phase 3
- Usage Ledger 成本结算：Phase 4
- 工具结果流式回填：Phase 3
- 视频问答与时间点跳转：M3+

---

## 八、非功能约束

### 8.1 性能

- SSE 流式首 Token 延迟：目标 < 3 秒（不含检索耗时）。
- 检索耗时：目标 < 2 秒（含向量搜索 + 结果构建）。
- 上下文预算：系统提示词 1500 Token + 用户输入 + 历史（按优先级裁剪）+ 证据片段 ≤ 8000 Token。

### 8.2 安全

- 所有请求需通过 Django 认证中间件。
- 用户只能访问自己课程的对话（通过 `course_id` 查 `user_id` 做权限校验）。
- 不在前端或日志中暴露 LLM API Key、完整 system prompt。

### 8.3 可审计

- 每次对话通过 `OrchestratorRun` 记录完整的技术轨迹。
- `ChatMessage` 记录用户可见的消息层面。
- 历史回答可定位当时的作用域修订和资料版本（通过 `orchestrator_run_id` 追溯）。

### 8.4 架构约束

- Agent 无状态（每次 `run()` 接收完整上下文）。
- 自建 Agent Runtime，不引入 LangChain/LangGraph。
- 通信走 SSE，不做 WebSocket。
- 模型不默认检索用户整个资源库，只看当前课程激活作用域。
- 不把聊天记录当作掌握度（端到端方案 §21 明确禁止）。

---

## 九、前端界面参考

课程工作台中的「提问」标签页布局参考（参见 `learning-plan-redesign-v10.md` 中的调整模式 UI 布局）：

```
┌──────────────────────────────────────────┐
│  提问                                    │
├──────────────────────────────────────────┤
│                                          │
│  对话历史区域（可滚动）                    │
│  ┌──────────────────────────────────┐    │
│  │                           [用户] │    │
│  │    什么是冯·诺依曼结构？          │    │
│  │                                  │    │
│  │ [AI]                             │    │
│  │    冯·诺依曼结构由五大部分组成：    │    │
│  │    运算器、控制器、存储器、        │    │
│  │    输入设备、输出设备…             │    │
│  │    📎 计组教材 p.23-25            │    │
│  │    📎 老师的PPT 第15页            │    │
│  └──────────────────────────────────┘    │
│                                          │
│  ┌──────────────────────────┬──────┐    │
│  │ 输入你的问题…              │ 发送 │    │
│  └──────────────────────────┴──────┘    │
└──────────────────────────────────────────┘
```

左侧或许可以列出该课程的会话列表，方便切换。

---

> @see docs/architecture/agent-runtime-design.md  
> @see docs/architecture/end-to-end-implementation-plan.md  
> @see docs/architecture/adr/0007-controlled-agent-tool-loop.md  
> @see docs/design/plans/2026-06-17-agent-runtime-phase1-plan.md  
> @see docs/design/plans/2026-06-17-agent-runtime-phase2-plan.md
