# Agent Runtime 开发进度（Phase A-D 完成）

> 更新日期：2026-06-30  
> 分支：`lh`  
> 状态：Phase A ✅ / Phase B ✅ / Phase C ✅ / Phase D ✅

---

## Phase A — API 规范化与 Swagger 集成 ✅

| 任务 | 说明 |
|------|------|
| A1 | `chat_api` 添加完整 `@extend_schema`（request / responses 200/400/500/503） |
| A2 | `chat_stream` 添加完整 `@extend_schema`（含 `text/event-stream` content-type） |
| A3 | 创建 `agent_runtime/urls.py`，`config/urls.py` 改为 `include()` 方式引入 |
| A4 | 新增 `GET /api/runs/` — Agent 运行历史列表（支持 limit/offset 分页） |
| A5 | 新增 `GET /api/runs/{run_id}/` — 单次运行详情（含 sub_runs + tool_invocations） |

**涉及文件**：`views.py` + `urls.py` + `config/urls.py`

**技术决策**：
- Swagger 标注采用统一 inline schema 模式，不创建额外 serializer 类
- 审计查询端点直接使用 Django ORM，不经过 RunManager
- URL 路径保持兼容，前端无需改动

---

## Phase B — Pipeline HTTP 端点 + 引文提取修复 ✅

### B1 — Pipeline 非流式端点

新增 `POST /api/chat/pipeline/`，前端通过 HTTP 直接调用多步 Agent Pipeline。

### B2 — Pipeline SSE 流式端点

新增 `POST /api/chat/pipeline/stream/`，逐步骤推送 SSE 事件（step_started / step_completed / done）。在 view 层直接编排步骤循环，不修改 `Orchestrator.run_stream()`。

### B3/B4 — 引文提取数据流修复

**问题**：`AgentOutput.citations` 始终为空 `[]`。

**根因**：`_extract_tool_citations(result)` 已正确提取引文，但只发给 SSE EventEmitter，未回填到 `AgentOutput`。3 个 Agent 的 `_extract_citations(ChatResponse)` 签名错误，始终返回 `[]`。

**修复**：

| 文件 | 改动 |
|------|------|
| `agents/turn_loop.py` | `_execute_tool` 返回 `(record, content, citations)` 三元组；累积 citations 填入 `AgentOutput`；移除 `extract_citations` 回调参数 |
| `agents/{tutor,planner,assessor}.py` | 删除 `_extract_citations()` 死代码 |

**修复后数据流**：`ToolResult` → `_extract_tool_citations()` → 累积 → `AgentOutput.citations` → 前端展示。

---

## Phase C — workflow_runtime 持久化状态机模块 ✅

### C1 — 模块骨架

新建 `mentora/workflow_runtime/` Django app（`__init__.py`、`apps.py`、`models.py`、`migrations/`）。

**WorkflowState**（表 `workflow_runtime_state`）：9 字段 + 3 索引，记录工作流完整生命周期（pending → running → completed/failed）。

**WorkflowLease**（表 `workflow_runtime_lease`）：4 字段 + 2 索引，Celery worker 租约防重复执行。

### C2 — WorkflowRuntime 服务

`services.py`（~150 行），9 个方法：

| 方法 | 职责 |
|------|------|
| `submit()` | 创建 pending 状态 |
| `claim_next()` | `select_for_update(skip_locked=True)` 原子认领 |
| `complete()` / `fail()` | 终态写回 |
| `checkpoint()` | 保存检查点 |
| `renew_lease()` | 延长租约 |
| `recover_stalled()` | 释放过期租约，重置为 pending |
| `get()` / `list_by_owner()` | 查询 |

### C3 — Celery 任务

`tasks.py` — `run_workflow(workflow_id)`：从 DB 加载 → 反序列化 `OrchestratorTask` → 执行 → 写回结果。支持自动重试（max_retries=2）。

`config/settings.py` 追加 `"mentora.workflow_runtime.tasks.*": {"queue": "agent"}`。

### C4 — HTTP 端点

3 个端点（均含 `@extend_schema`）：

| 方法 | URL | 说明 |
|------|-----|------|
| `POST` | `/api/workflows/submit/` | 提交异步 workflow |
| `GET` | `/api/workflows/{id}/` | 查询状态 + 结果 |
| `GET` | `/api/workflows/` | 用户 workflow 列表 |

### C5 — 注册验证

- `INSTALLED_APPS`：`"mentora.workflow_runtime"`
- `CELERY_TASK_ROUTES`：`{"queue": "agent"}`
- `config/urls.py`：`include("mentora.workflow_runtime.urls")`

---

## Phase D — 生产加固 ✅

### D1 — 请求频率限流

参考 LightRead `rate_limit.py` 的 Redis 滑动窗口 + 装饰器模式。

**新建** `agent_runtime/decorators.py`：`@rate_limit(key_prefix, max_attempts, window_seconds)` 装饰器，以 IP 为粒度。

**安装** `django-redis`，`config/settings.py` 新增 `CACHES` Redis 后端配置。

**挂载**：

| 端点 | 限流 |
|------|------|
| `chat_api` | 10 次/分钟 |
| `chat_stream` | 5 次/分钟 |
| `pipeline_chat` | 3 次/2 分钟 |

超限返回 `429 {error, retry_after}`。

### D2 — SSE 断线恢复

**不做**。参考 LightRead 同样未实现此功能——生产级项目也依赖客户端断线后重新发送完整请求。

### D3 — 核心流程测试

**新增 5 个测试**，与已有 4 个回归测试合计 **9/9 通过**。

| 测试 | 文件 |
|------|------|
| `test_citations_accumulate_from_tool_results` | `test_agent_loop.py` |
| `test_citations_empty_when_tool_returns_no_results` | `test_agent_loop.py` |
| `test_rate_limit_allows_within_window` | `test_rate_limit.py` |
| `test_rate_limit_blocks_when_exceeded` | `test_rate_limit.py` |
| `test_rate_limit_ip_isolation` | `test_rate_limit.py` |

---

## 涉及文件总览

```
apps/api/
├── config/
│   ├── settings.py                    # CACHES + workflow_runtime 注册 + task routes
│   └── urls.py                        # agent_runtime + workflow_runtime include
├── mentora/
│   ├── agent_runtime/
│   │   ├── views.py                   # 6 端点（chat×2 + pipeline×2 + run×2）
│   │   ├── urls.py                    # 模块路由（新）
│   │   ├── decorators.py              # rate_limit 装饰器（新）
│   │   ├── schemas/task.py            # agent_role/user_message 可选
│   │   └── agents/
│   │       ├── turn_loop.py           # 引文修复（_execute_tool 三元组）
│   │       ├── tutor.py               # 清理 _extract_citations
│   │       ├── planner.py             # 清理 _extract_citations
│   │       └── assessor.py            # 清理 _extract_citations
│   └── workflow_runtime/              # 新模块
│       ├── __init__.py / apps.py
│       ├── models.py                  # WorkflowState + WorkflowLease
│       ├── services.py                # WorkflowRuntime（9 方法）
│       ├── tasks.py                   # run_workflow Celery 任务
│       ├── views.py / urls.py         # 3 个 HTTP 端点
│       └── migrations/0001_initial.py
├── tests/
│   ├── test_agent_loop.py             # +2 引文测试
│   └── test_rate_limit.py             # +3 限流测试（新）
└── pyproject.toml                     # +django-redis

docs/development/agent-runtime-phase-ab.md  # 本文档
```
