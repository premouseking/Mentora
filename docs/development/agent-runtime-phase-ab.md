# Agent Runtime 开发进度（Phase A + B）

> 更新日期：2026-06-29  
> 分支：`lh`  
> 状态：Phase A ✅ / Phase B ✅ / Phase C 待启动

## Phase A — API 规范化与 Swagger 集成 ✅

### 完成内容

| 任务 | 说明 |
|------|------|
| A1 | `chat_api` 添加完整 `@extend_schema`（request / responses 200/400/500/503） |
| A2 | `chat_stream` 添加完整 `@extend_schema`（含 `text/event-stream` content-type） |
| A3 | 创建 `agent_runtime/urls.py`，`config/urls.py` 改为 `include()` 方式引入 |
| A4 | 新增 `GET /api/runs/` — Agent 运行历史列表（支持 limit/offset 分页） |
| A5 | 新增 `GET /api/runs/{run_id}/` — 单次运行详情（含 sub_runs + tool_invocations） |

### 涉及文件

- `agent_runtime/views.py` — 扩展 `chat_api`/`chat_stream` 的 Swagger 标注，新增 `run_list` + `run_detail`
- `agent_runtime/urls.py` — 新建模块路由文件（4 条路由）
- `config/urls.py` — 从直接 import 改为 `include("mentora.agent_runtime.urls")`

### 技术决策

- Swagger 标注采用项目统一模式：inline `request={"application/json": {...}}`，不创建额外 serializer 类
- 审计查询端点直接使用 Django ORM，不经过 RunManager（后者仅负责写入）
- URL 路径保持兼容（`/api/chat/`、`/api/chat/stream/`），前端无需改动

---

## Phase B — Pipeline HTTP 端点 + 引文提取修复 ✅

### B1 — Pipeline 非流式端点

新增 `POST /api/chat/pipeline/`，支持前端通过 HTTP 直接调用多步 Agent Pipeline。

请求体：
```json
{
  "pipeline_steps": [
    {"agent_role": "clarifier", "task_instruction": "...", "output_key": "step1", "max_tool_rounds": 0},
    {"agent_role": "planner", "task_instruction": "...", "output_key": "step2", "input_from": "step1"}
  ],
  "context_sources": []
}
```

响应体包含 `steps` 数组（每步的 `finish_reason`、`content_preview`、`full_content`、`citations`、`usage`）和 `total_duration_ms`。

配合修改了 `OrchestratorTask` schema：`agent_role` 和 `user_message` 改为可选字段（Pipeline 模式下无需这两个字段）。

### B2 — Pipeline SSE 流式端点

新增 `POST /api/chat/pipeline/stream/`，以 SSE 事件流返回每步进度：

```
data: {"type":"step_started","step_index":0,"agent_role":"clarifier","output_key":"step1"}
data: {"type":"step_completed","step_index":0,...,"finish_reason":"completed","usage":{...}}
data: {"type":"done","total_duration_ms":8234}
```

实现策略：在 view 层直接编排步骤循环（复用 `orch._agents`），不修改 `Orchestrator.run_stream()`（后者仅支持单 Agent 逐 token 流式，与 Pipeline 逐步骤流式不同质）。

### B3/B4 — 引文提取数据流修复

**问题**：`AgentOutput.citations` 始终为空 `[]`，前端无法展示引用来源。

**根因**：`turn_loop.py` 的 `_extract_tool_citations(result)` 已正确提取引文，但只发给 SSE EventEmitter，未回填到 `AgentOutput`。3 个 Agent 的 `_extract_citations(ChatResponse)` 签名错误（引文在工具结果中而非模型文本回复中），始终返回 `[]`。

**修复**：

| 文件 | 改动 |
|------|------|
| `agents/turn_loop.py` | `_execute_tool` 返回值从 `(record, content)` 扩展为 `(record, content, citations)`；`run_tool_loop` / `run_tool_loop_stream` 累积所有 citations 填入 `AgentOutput`；移除 `extract_citations` 回调参数；移除未使用的 `Callable` import |
| `agents/tutor.py` | 删除 `_extract_citations()` 死代码；`run()` / `run_stream()` 不再传 `extract_citations=` |
| `agents/planner.py` | 同上 |
| `agents/assessor.py` | 同上 |

**修复后数据流**：`ToolResult` → `_extract_tool_citations()` → 累积到 `all_citations` → `AgentOutput.citations` → 前端展示。

### 涉及文件（Phase B）

| 文件 | 改动量 |
|------|--------|
| `agent_runtime/views.py` | +292 行（`pipeline_chat` + `pipeline_chat_stream`） |
| `agent_runtime/urls.py` | +2 路由 |
| `agent_runtime/schemas/task.py` | `agent_role`/`user_message` 改为可选 |
| `agent_runtime/agents/turn_loop.py` | 核心修复（`_execute_tool` 返回三元组 + 累积 citations） |
| `agent_runtime/agents/tutor.py` | 删除死代码 |
| `agent_runtime/agents/planner.py` | 删除死代码 |
| `agent_runtime/agents/assessor.py` | 删除死代码 |

---

## 整体进度

```
Phase A ████████████████████████ 100%  已完成
Phase B ████████████████████████ 100%  已完成
Phase C ░░░░░░░░░░░░░░░░░░░░░░░░   0%  待启动
Phase D ░░░░░░░░░░░░░░░░░░░░░░░░   0%  待启动
```

## 下一步

Phase C — workflow_runtime 持久化状态机模块（C1-C5 共 5 个子任务），见 [Phase C 方案](#)（审批中）。
