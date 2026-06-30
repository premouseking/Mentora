# 实现变更记录

本文件记录对架构、工程结构或协作方式有影响的**重要实现改动**。
日常小修小补、纯样式调整或单测补充不写入此处；对应 ADR 或阶段任务状态
在各自文档中维护。

记录格式：

```text
## YYYY-MM-DD：<简短标题>

关联：ADR / 设计文档 / 阶段任务
状态：骨架 | 部分可用 | 已验收

### 做了什么
### 影响范围
### 尚未完成 / 已知限制
### 验证方式
```

---

## 2026-06-17：Agent 运行时与模型网关 Phase 1 骨架落地

关联：

- [agent-runtime-design.md](../architecture/agent-runtime-design.md)
- [Phase 1 实施计划](../design/plans/2026-06-17-agent-runtime-phase1-plan.md)

状态：**骨架已落地**（25 集成测试通过，FakeProvider 驱动）

### 做了什么

新增 `model_gateway` 模块（14 文件 / ~806 行）和扩展 `agent_runtime` 模块（20+ 新文件 / ~2,143 行）。

| 模块 | 关键文件 | 说明 |
| --- | --- | --- |
| model_gateway | `gateway.py` | ModelGateway 主入口，`chat(task_type, messages, tools)` + audit_enabled 开关 |
| model_gateway | `router.py` | TaskRouter：task_type → provider 映射 |
| model_gateway | `schemas.py` | Message / ChatResponse / ProviderResponse / ToolCall DTO |
| model_gateway | `structured_output.py` | Pydantic JSON Schema 校验器 |
| model_gateway | `providers/base.py` | BaseProvider 抽象类 |
| model_gateway | `providers/fake.py` | FakeProvider：文本响应 / 工具调用场景 / 错误注入 |
| model_gateway | `models.py` | ModelRequest / ModelAttempt 审计模型 |
| agent_runtime | `schemas/task.py` | OrchestratorTask / PipelineStep / BudgetConfig |
| agent_runtime | `schemas/output.py` | AgentOutput / OrchestratorResult / Citation |
| agent_runtime | `schemas/context.py` | AgentContext / ToolContext / ContextAllocation |
| agent_runtime | `prompts/manager.py` | PromptManager：JSON 模板加载 / 缓存 / Jinja2 式变量渲染 |
| agent_runtime | `prompts/templates/tutor.json` | TutorAgent 系统提示词 |
| agent_runtime | `context/manager.py` | ContextManager：上下文预算控制 + P0-P4 优先级裁剪 |
| agent_runtime | `context/token_counter.py` | TokenCounter：字符数 // 4 近似估算 |
| agent_runtime | `tools/base.py` | ToolDefinition / Tool 抽象 / ToolResult / ToolContext |
| agent_runtime | `tools/registry.py` | ToolRegistry：注册 / 按角色过滤 / OpenAI 格式导出 |
| agent_runtime | `tools/knowledge_tools.py` | retrieve_evidence 占位工具 |
| agent_runtime | `agents/base.py` | Agent 基类 + AgentInput |
| agent_runtime | `agents/orchestrator.py` | Orchestrator：单 Agent 模式 + Pipeline 模式骨架 |
| agent_runtime | `agents/tutor.py` | TutorAgent：工具调用循环实现 |
| agent_runtime | `events.py` | EventEmitter 回调模式（thinking / tool.call / completed 等） |
| agent_runtime | `models.py` | OrchestratorRun / SubAgentRun / ToolInvocation / PromptRevision |
| agent_runtime | `services.py` | RunManager：运行记录 CRUD |
| agent_runtime | `tasks.py` | Celery 任务骨架 `run_agent` |

工程层面：
- `apps/api/config/settings.py` 注册 `"mentora.model_gateway"` 到 `INSTALLED_APPS`
- 两个模块各含 `migrations/0001_initial.py`（手动编写，因缺少 PyMuPDF 无法 `makemigrations`）
- 提示词模板改用 JSON 格式（环境无 PyYAML）

### 核心设计决策

| 决策 | 理由 |
|------|------|
| Agent 无状态 | 每次 `run()` 接收完整上下文，不耦合数据库 |
| FakeProvider 确定性测试 | 无需真实 LLM 即可验证工具调用循环正确性 |
| 粗 Token 计数（`len // 4`） | 避免 tiktoken 依赖，误差在可接受范围 |
| Phase 1 非流式 | 先验证核心循环正确性，流式在 Phase 2 |
| audit_enabled 开关 | 测试环境无需 PostgreSQL 即可运行 |
| sync_to_async 包装 Django ORM | 支持全异步 Agent 循环 |

### 影响范围

- **WH**：model_gateway 作为独立模块，通过 audit_enabled 可在无 DB 环境测试
- **LBZ**：无直接前端影响；后续对话接口消费 SSE 事件和结构化输出
- **LH**：knowledge_tools.py 中的 retrieve_evidence 为占位实现，待对接 retrieval.search
- **LWJ**：Agent 体系骨架就绪，后续 PlannerAgent / AssessorAgent 继承 Agent 基类即可

### 尚未完成 / 已知限制

- OpenAIProvider 尚未实现（Phase 2）
- Pipeline 模式仅有骨架，端到端未验证（Phase 2）
- retrieve_evidence 为占位工具，返回预设数据而非真实检索
- SSE 事件为回调模式（无流式，Phase 2）
- PromptManager 仅支持 `{{ var }}` 和 `{{var}}` 两种占位符格式
- Django migration 为手动编写，首次 `migrate` 后需验证

### 验证方式

```bash
# 单元 + 集成测试（FakeProvider 驱动，无需 DB）
python apps/api/tests/run_integration_tests.py
# 输出：25/25 通过，覆盖无工具 / 单轮工具 / 多轮工具 / 最大轮次 / 错误场景

# 模块导入正确性
python -c "from mentora.model_gateway.gateway import ModelGateway; print('OK')"
python -c "from mentora.agent_runtime.agents.orchestrator import Orchestrator; print('OK')"
```

---

## 2026-06-17：Agent 运行时 Phase 2 — OpenAIProvider + 流式 + Planner/Clarifier + Pipeline

关联：

- [agent-runtime-design.md](../architecture/agent-runtime-design.md) §14
- [Phase 2 实施计划](../design/plans/2026-06-17-agent-runtime-phase2-plan.md)

状态：**骨架已落地**（新增 8 文件 / ~600 行，模块导入验证通过，非 DB 单元测试通过）

### 做了什么

| 模块 | 关键文件 | 说明 |
| --- | --- | --- |
| model_gateway | `providers/http_client.py` | 自建异步 HTTP 客户端：`async_post_json()`（asyncio.to_thread + urllib）+ `async_post_sse()`（asyncio.open_connection + SSL 手动 HTTP/1.1 + SSE 解析） |
| model_gateway | `providers/openai.py` | OpenAIProvider：非流式 `chat()` + 流式 `chat_stream()`，兼容 Function Calling，tool_calls delta 跨 chunk 汇总 |
| model_gateway | `providers/base.py` | 新增可选 `chat_stream()` 方法（默认 `NotImplementedError`） |
| model_gateway | `providers/fake.py` | 新增 `chat_stream()`：文本逐 4 字符分组流式输出 + 工具调用场景 |
| model_gateway | `gateway.py` | 新增 `chat_stream()`：流式 Provider 包装 + 审计记录（流结束后统一记录） |
| agent_runtime | `agents/planner.py` | PlannerAgent：基于目标和资料生成学习计划，使用 `retrieve_evidence` 工具 |
| agent_runtime | `agents/clarifier.py` | ClarifierAgent：意图澄清，纯文本交互，不使用工具 |
| agent_runtime | `agents/tutor.py` | 新增 `run_stream()`：流式工具调用循环，逐 chunk 推送 + 事件发射 |
| agent_runtime | `agents/orchestrator.py` | Pipeline 增强：`step_started`/`step_completed` 事件 + 单步失败不会崩溃 |
| agent_runtime | `events.py` | 新增 `agent_response_stream`、`step_started`、`step_completed` 事件 |
| prompts | `templates/planner.json` | PlannerAgent 系统提示词 |
| prompts | `templates/clarifier.json` | ClarifierAgent 系统提示词 |
| config | `settings.py` | 新增 LLM 配置（`LLM_API_KEY` / `LLM_API_BASE_URL` / `LLM_MODEL`，文件内直接配置） |
| tests | `test_agent_runtime.py` | 新增 18 个测试：FakeProvider 流式、Tutor 流式、Planner/Clarifier、Pipeline E2E、Gateway 流式 |

### 核心设计决策

| 决策 | 理由 |
|------|------|
| 自建 HTTP 客户端（零依赖） | 环境无 `openai`/`httpx`/`aiohttp`，stdlib 完全可行 |
| `asyncio.open_connection` 做 SSE | 避免 asyncio.to_thread 阻塞流式读取 |
| tool_calls delta 跨 chunk 聚合 | OpenAI 流式协议逐字段补全，O(1) 索引查找 |
| LLM 配置在 `settings.py` 文件内 | 用户明确要求不用环境变量 |
| `chat_stream()` 为可选方法 | 不破坏 FakeProvider 兼容性 |
| Pipeline 错误记录 partial 结果 | 调用方可自行决策是否重试 |

### 影响范围

- LLM 配置由 `settings.py` 的 `LLM_API_KEY` 读取（当前未填入，需填入后方可调用真实 API）
- LBZ：TutorAgent 新增 `run_stream()` 支持 SSE 流式，后续对话 API 可逐 chunk 推送
- LWJ：PlannerAgent / ClarifierAgent 就绪，可在此基础上开发 AssessorAgent
- WH：自建 HTTP 客户端纯 stdlib，无新增依赖

### 尚未完成 / 已知限制

- `LLM_API_KEY` 未填入，OpenAIProvider 不可用（需用户填入后测试）
- Pipeline `input_from` 传递原始文本；后续可结构化传递
- PlannerAgent / ClarifierAgent 未实现 `chat_stream`
- retrieve_evidence 仍为占位工具（待 retrieval 模块）

### 验证方式

```bash
# 模块导入验证（已通过）
python -c "from mentora.model_gateway.providers.openai import OpenAIProvider; \
from mentora.agent_runtime.agents.clarifier import ClarifierAgent; print('OK')"

# 非 DB 单元测试（已通过 6+）
python -m pytest apps/api/tests/test_agent_runtime.py -k "not django_db" --noconftest -q
```

---

## 2026-06-18：Agent 运行时流式 SSE 接入 + 前后端联调

关联：

- [agent-runtime-design.md](../architecture/agent-runtime-design.md) §14
- [Phase 2 实施计划](../design/plans/2026-06-17-agent-runtime-phase2-plan.md)

状态：**已验收**（DeepSeek API 真实调用，流式逐字输出可用）

### 做了什么

| 层级 | 文件 | 说明 |
| --- | --- | --- |
| Agent | `orchestrator.py` | 新增 `run_stream()` 异步生成器，通过 `asyncio.Queue` + EventEmitter 桥接 `TutorAgent.run_stream()`，逐 chunk 产出 SSE 事件字符串 |
| HTTP | `views.py` | 新增 `chat_stream` 同步视图 `POST /api/chat/stream/`，返回 `StreamingHttpResponse(content_type="text/event-stream")`。WSGI 兼容性适配：同步生成器内建 event loop 手动迭代异步生成器 |
| 路由 | `urls.py` | 注册 `api/chat/stream/` |
| 前端 | `vite.config.ts` | 添加 proxy `"/api" → "http://127.0.0.1:8000"` |
| 前端 | `AppShell.tsx` | `handleSend` 改为 `fetch + ReadableStream` 逐行解析 SSE `data:` 事件，实时拼接 assistant 消息内容 |

### 联调修复

| 问题 | 根因 | 修复 |
|------|------|------|
| 前端「无法连接」 | Vite 未配代理，请求发到 `localhost:5173` 而非 Django `8000` | `vite.config.ts` 添加 `proxy: { "/api": "http://127.0.0.1:8000" }` |
| `ECONNREFUSED 127.0.0.1:8000` | Django 未启动 | 启动 `runserver` + Docker 基础设施 |
| Django 启动崩溃 | 缺少 PyMuPDF (`fitz`) | `pip install -e .` 安装依赖 |
| Django SystemCheckError | `ModelAttempt` 索引名 `mgw_attempt_success_created_idx` 超 30 字符 | 缩短为 `mgw_att_succ_created_idx` |
| LLM 返回空回复 | `.env` 解析器"首次优先"策略：注释行 `# DeepSeek API Key` 被当作 key 值，真正 key 被跳过 | 删除 `.env` 中重复注释行 |
| 流式响应被缓冲 | WSGI 模式下异步 `StreamingHttpResponse` 不流式 | `chat_stream` 改为同步视图，内建 event loop 手动迭代异步生成器 |

### 核心设计决策

| 决策 | 理由 |
|------|------|
| WSGI 兼容同步视图 | `runserver` WSGI 模式下异步 `StreamingHttpResponse` 会被缓冲，同步视图 + `asyncio.new_event_loop()` 手动桥接保证 chunk-by-chunk 输出 |
| SSE 格式：`data: {"type":"chunk","content":"…"}\n\n` | 与 EventEmitter 的 `agent_response_stream` 事件对齐，前端按行解析 |
| 前端 `setMessages` 每 chunk 更新一次 | 简单有效；后续可 batched 优化 |

### 影响范围

- **LBZ**：前端 AI 面板已接入真实流式对话，用户体验完整
- **WH**：Vite proxy 配置已落地，开发环境前后端联通
- **LWJ**：Agent 运行时 Phase 1/2 通过真实 LLM 端到端验收
- **LH**：`retrieve_evidence` 仍为占位工具，待对接 retrieval 模块

### 验证方式

```bash
# 启动基础设施
pnpm infra:up

# 后端（终端 1）
cd apps/api
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

# 前端（终端 2）
pnpm dev:web

# 浏览器打开 AI 面板发消息 → 逐字流式输出
```

---

## 2026-06-13：移除 Deep Link，统一应用内登录

关联：

- [desktop-client-architecture.md](../architecture/desktop-client-architecture.md) §5.3、§8、§12
- [ADR-0005](../architecture/adr/0005-electron-desktop-client.md)
- [end-to-end-implementation-plan.md](../architecture/end-to-end-implementation-plan.md) §12.4、M0

状态：**已落地**

### 做了什么

- 删除 `apps/desktop/src/main/deepLink.ts` 及 `mentora://` 自定义协议注册（`electron-builder.yml` `protocols`）。
- 移除 IPC 通道 `window.deep-link`、`DeepLink` 类型与 `window.onDeepLink` preload 暴露。
- `bootstrap.ts` 保留单实例锁，第二实例仅聚焦已有窗口；不再监听 `open-url` 或解析启动参数中的协议 URL。
- 同步架构文档：认证改为 renderer 经 `auth.login` / `auth.register` IPC 提交凭据，主进程调用 Django 并保存 Refresh Token。

### 影响范围

- 桌面认证路径与 `apps/desktop/src/main/auth.ts` 现实现一致，不再预留系统浏览器 OAuth / PKCE 回调。
- `shell.openExternal` 仍用于打开外部帮助链接等，不参与登录。

### 尚未完成 / 已知限制

- 登录/注册 IPC 骨架已有，**尚未与 Django 真实端点端到端验收**。
- 通知点击内部路由（`notifications.onActivated`）仍走 IPC 事件，不依赖自定义 URL 协议。

### 验证方式

```bash
pnpm --dir apps/desktop typecheck
pnpm dev:desktop   # 开发态默认 dev auth bypass；设 MENTORA_DEV_AUTH_BYPASS=0 可验证登录 UI
```

---

## 2026-06-13：Electron 桌面客户端框架骨架

关联：

- [desktop-client-architecture.md](../architecture/desktop-client-architecture.md)
- [ADR-0005](../architecture/adr/0005-electron-desktop-client.md)
- [stage-01-backlog.md](./stage-01-backlog.md)（P1-LBZ-01 上传流程的前置宿主）

状态：**骨架**（main/preload/shared 已落地，业务链路尚未端到端验收）

### 做了什么

新增 `apps/desktop/`，按设计文档 §11 目标目录实现 Electron 薄宿主：

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 共享契约 | `src/shared/channels.ts` | `mentora:<domain>:<action>` IPC 注册表 |
| 共享契约 | `src/shared/desktopApi.ts` | `window.mentoraDesktop` TypeScript 类型 |
| 共享契约 | `src/shared/schemas.ts` | main 侧 zod 权威校验（相对 API 路径、外部 URL 等） |
| 主进程 | `src/main/index.ts` | 崩溃保护入口，业务前注册 handler |
| 主进程 | `src/main/bootstrap.ts` | 单实例锁、生命周期 |
| 主进程 | `src/main/window.ts` | 安全基线（sandbox、CSP、导航拦截） |
| 主进程 | `src/main/auth.ts` | safeStorage + 应用内登录/注册 + 单飞刷新 |
| 主进程 | `src/main/apiClient.ts` | 认证 API 桥 + 路径 allowlist + 401 重试 |
| 主进程 | `src/main/eventStreams.ts` | SSE 桥（stream_id、Last-Event-ID、renderer 销毁清理） |
| 主进程 | `src/main/fileTokens.ts` | 短期、窗口绑定的 `file_token` |
| 主进程 | `src/main/uploads.ts` | 流式直传对象存储 + SHA-256（待后端对接） |
| 主进程 | `src/main/updater.ts` | electron-updater 包装（dev/unpacked 跳过） |
| 主进程 | `src/main/ipc/index.ts` | 按能力域逐个 `ipcMain.handle`，无万能 channel |
| Preload | `src/preload/index.ts` | `contextBridge` 暴露受控 API，事件返回 unsubscribe |

工程与脚本：

- `pnpm-workspace.yaml` 注册 `apps/desktop`
- 根 `package.json`：`dev:desktop`、`build:desktop`、`dist:desktop`；`pnpm.onlyBuiltDependencies` 放行 electron 二进制下载
- `apps/desktop`：`tsup` 编译 main/preload 为 CJS；`electron-builder.yml`（Windows NSIS + generic 更新源）
- 开发态加载 `apps/web` Vite（`http://localhost:5173`，HMR）；`tsup --watch` + `nodemon` 在主/preload 变更时重启 Electron；打包态加载 `../web/dist` → `resources/renderer`
- `README.md`、`.env.example` 补充桌面开发说明（`MENTORA_API_BASE_URL`）

### 影响范围

- **WH**：Main/Preload 骨架已就绪；后续 P1 上传链路应通过 `window.mentoraDesktop.files` / `uploads` / `api` 接入，不再在 renderer 直接使用浏览器文件路径
- **LBZ**：renderer 可通过 `window.mentoraDesktop` 类型契约集成；`apps/web` 暂不重命名，仍作 renderer
- **LH / LWJ**：无直接代码影响；上传与 SSE 仍走云端 Django
- **阶段一风险**：「Electron Host 尚未实现」已降级为「骨架已落地，待与上传 API 联调验收」

### 尚未完成 / 已知限制

- 登录、上传、SSE 等 IPC 已实现骨架，**尚未与 Django 真实端点联调**
- 文档 §12 要求的完整 IPC/SSE/认证 E2E **未编写**；Electron GUI 基线 smoke 已补充
- Windows 代码签名与生产更新 feed 仍为占位配置（`electron-builder.yml` → `updates.example.com`）
- ADR-0005 仍为 Proposed；端到端验收通过后再改为 Accepted

### 验证方式

```bash
pnpm install
pnpm --dir apps/desktop typecheck    # 已通过
pnpm --dir apps/desktop build:bundle # 已通过
pnpm --dir apps/desktop exec electron --version  # v33.4.11

# 本地联调（需 infra + API + Vite）
pnpm dev:desktop
```

建议提交信息（供 git commit 时使用）：

```text
feat: 搭建 Electron 桌面客户端框架骨架

新增 apps/desktop（main/preload/shared），实现 typed IPC 桥、安全窗口基线、
认证/上传/SSE/更新骨架；注册 workspace 脚本与 electron-builder 配置，
开发态加载 apps/web renderer。
```

---

## 2026-06-13：Electron GUI 冒烟验收

关联：`apps/desktop/scripts/smoke.mjs`、`pnpm smoke:desktop`

状态：**已验收**

### 自动验收

- 新增 `pnpm smoke:desktop`，自动编译 main/preload、启动 Vite 并通过 Playwright 启动真实 Electron。
- 验证主窗口加载、`window.mentoraDesktop` 注入、`app.getInfo()`、Node.js 隔离和窗口控制 IPC。
- 新增跨平台子进程树清理模块及 Node.js 单元测试。
- Windows 下通过 `ComSpec` 启动 pnpm，避免 Node.js 24 直接 `spawn pnpm.cmd` 返回 `EINVAL`。

### 本机 GUI 验收

- `pnpm dev:desktop` 成功显示 Mentora 开发窗口。
- Electron main 完成 bootstrap 和 IPC 注册，renderer 从 `http://localhost:5173` 加载。
- 窗口可最小化、最大化、还原和关闭。
- 关闭后，本轮启动的 Electron、Vite、tsup watch 和 concurrently 进程树均已退出。
- DevTools 自身存在 Chromium protocol/style 控制台告警；renderer smoke 未发现 uncaught page error。

### 尚未覆盖

- 真实登录/注册与后端联调。
- PDF 上传与对象存储。
- SSE 断线恢复。
- 安装包与自动更新。

---

## 2026-06-13：桌面开发态

关联：`apps/desktop/build/icon.ico`、`apps/desktop/src/main/window.ts`

状态：**部分可用**

### 做了什么

- **开发态 renderer**：保留 Vite dev server（`http://localhost:5173`）+ HMR；Electron 经 `MENTORA_DEV_SERVER_URL` 加载，不再尝试 `file://` + `vite build --watch` 整页重载方案。
- **开发态 main/preload**：`apps/desktop` 的 `dev` 脚本增加 `nodemon`，监听 `dist/main/index.cjs` 与 `dist/preload/index.cjs`，编译产物变更后自动重启 Electron（对齐 LighTest 的 `dev:electron` 模式）。
- **路由**：`apps/web` renderer 使用 `HashRouter`，避免打包态 `loadFile` 下 BrowserRouter 子路由刷新白屏。
- **Windows 开发图标**：开发态 Windows 使用 `build/icon.ico` + `app.setAppUserModelId("com.mentora.desktop")`；`BrowserWindow` 经 `nativeImage.createFromPath` 加载图标。

### 影响范围

- 日常桌面开发仍用 `pnpm dev:desktop`（根脚本 concurrently 启动 Vite 与 desktop dev）。
- 改 web 页面 → Vite HMR；改 main/preload → tsup 重建 → nodemon 重启 Electron。
- 文档：`README.md`、`.env.example`、`CONTRIBUTING.md` 已同步桌面开发说明。

### 尚未完成 / 已知限制

- Windows 代码签名与生产更新 feed 仍为占位配置。
- 完整 Playwright Electron E2E 仍未建设。

### 验证方式

```bash
pnpm --dir apps/desktop typecheck
pnpm --dir apps/desktop build:bundle
pnpm test:desktop
pnpm dev:desktop   # 改 web 文案应 HMR；改 main 日志应自动重启；Windows 任务栏应显示 Mentora 图标
```
