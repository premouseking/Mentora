# CLAUDE.md

## Project

Mentora — Electron desktop course workspace for personalized learning.
Monorepo: `apps/web` (React/Vite renderer), `apps/api` (Django REST API + Celery),
`apps/desktop` (Electron host, planned).

## Commands

```bash
pnpm install                  # Install all workspace deps
pnpm infra:up                 # Start PostgreSQL, Redis, MinIO (Docker)
pnpm api:migrate              # Apply Django migrations
pnpm api:seed                 # Seed local development data
pnpm api:smoke:upload         # Verify upload/parse/evidence path
pnpm dev:api                  # Start Django API (http://localhost:8000)
pnpm dev:web                  # Start Vite dev server (http://localhost:5173)
pnpm build:web                # Production build
pnpm typecheck:web            # TypeScript check
pnpm test:web                 # Run frontend tests

# API (in apps/api)
cd apps/api && python manage.py runserver   # Django dev server (http://localhost:8000)
cd apps/api && python manage.py test        # Run backend tests
cd apps/api && celery -A config worker -l info  # Celery worker
```

## Project Skills

Repo-local agent workflows live under `docs/agents/skills/`.

- Use `docs/agents/skills/mentora-local-dev-smoke/SKILL.md` before local startup, API/Web/Desktop smoke verification, or dev infra debugging.
- Use `docs/agents/skills/mentora-runtime-boundary-review/SKILL.md` before reviewing mock data, hardcoded runtime values, fake fallback branches, or dev/prod boundary changes.

Local dev must keep `.env` untracked. Web `/api/*` should proxy through Vite to Django using root `.env` values. LLM-backed endpoints should return explicit 503 when `LLM_API_KEY` is not configured; do not restore mock success paths.

## Architecture

### Domain modules (Django apps under `apps/api/mentora/`)
- `courses` — course profile, knowledge scope revisions, dual-confirm activation
- `learning` — learning plans, tasks, sessions, mastery aggregation
- `assessment` — item bank, AI-generated questions, scoring, quality gates
- `knowledge` — sources, parsing, evidence, topics, retrieval (to be split)
- `agent_runtime` — workflow state machines, checkpoints, tool calls

### Infrastructure modules
- `desktop_host` — Electron main/preload, IPC, auth bridge, SSE
- `workflow_runtime` — persistent state machines, Celery tasks, leasing
- `runtime_events` — outbox pattern, recoverable SSE projections
- `model_gateway` — model routing, structured output, fallback, cost ledger

### Key constraints
- Sources belong to user library; courses reference them via versioned scopes
- `CourseProfileRevision` is immutable once confirmed; changes clone as new drafts
- `learning` cannot activate a plan independently; `courses` atomically activates both
- Model outputs are candidates only; domain services validate before persisting
- Renderer has no Node.js access; all system calls go through typed preload IPC
- No global Zustand store; use React Query for server state, local state per feature

## Tech stack
- Frontend: React 19, Vite, TypeScript (apps/web)
- Backend: Django, Django REST Framework, Celery (apps/api)
- Database: PostgreSQL + pgvector
- Cache/Queue: Redis
- Storage: MinIO (local) / COS (prod)
- Desktop: Electron (planned, apps/desktop)

## Documentation
- `docs/architecture/end-to-end-implementation-plan.md` — master implementation plan
- `docs/architecture/module-boundaries.md` — domain ownership and constraints
- `docs/architecture/technical-solution.md` — tech decisions and evolution log
- `docs/architecture/adr/` — Architecture Decision Records (5 ADRs)

## Git workflow
- Local branch: `lh` (all work happens here)
- Remote: `origin` → `https://github.com/premouseking/Mentora`
- Push target: `origin/course-ui`

## Git commit conventions

所有提交信息使用以下格式（来源 `.cursor/rules/git-commit.mdc`）：

```
<type>: <简短中文说明>

<一段具体的中文改动说明>
```

标题使用简体中文，控制在 50 字以内。正文说明修改了什么、影响哪些模块。常用类型：

| 类型 | 用途 |
| --- | --- |
| `feat` | 新增用户可见功能 |
| `fix` | 修复缺陷 |
| `refactor` | 不改变外部行为的代码重构 |
| `docs` | 仅修改文档 |
| `test` | 新增或调整测试 |
| `style` | 不影响逻辑的格式或视觉样式调整 |
| `perf` | 性能优化 |
| `chore` | 构建、依赖或工程维护 |
| `ci` | 持续集成配置 |
| `revert` | 撤销已有提交 |

## Code style

来源 `.cursor/rules/code-comments.mdc`。注释语言为简体中文。

**何时写注释：**
- 写：模块边界、安全/权限约束、非显而易见的业务规则、跨进程/跨层协议、架构文档对应关系
- 不写：类型与命名已自解释的 getter/setter、逐行复述代码、无意义的占位注释

**模块级注释（文件头）：**
```typescript
/**
 * <一句话职责>
 *
 * 约定：<命名、协议、数据形态等团队约定>
 *
 * 约束：
 * - <调用方必须遵守的规则>
 * - <禁止的行为>
 *
 * @see docs/architecture/... §x.x
 * @module path/to/module
 */
```

**行内注释：**
- 只解释**为什么**（权衡、平台差异、安全原因），不解释做了什么
- 多步骤流程用编号 `// 1. …`，一步一行
- 禁止 `// TODO: fix later`；若必须留 TODO，写清阻塞条件与预期行为

**禁止：**
- 英文注释（协议字面量、第三方 API 字段名除外）
- 复述标识符（`// 获取用户信息` 放在 `getUserInfo()` 上）
- 无约束的泛泛描述（`// 处理请求`、`// 初始化`）
- 注释与实现不一致；改代码时同步改注释
