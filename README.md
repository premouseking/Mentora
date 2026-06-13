# Mentora

Mentora is an Electron desktop course workspace for personalized learning.
Sources live in a reusable user library. Each course references an explicit,
versioned knowledge scope and owns its learning intents, plans, learning
events, assessments, and actionable learning map.

## Repository layout

```text
apps/
  desktop/      Electron main/preload thin host (main + preload + shared IPC)
  web/          React/Vite renderer (loaded by the desktop host)
  api/          Django REST API, SSE, Celery, and domain workflows
docs/
  architecture/ Architecture and module boundary documents
infra/
  docker/       Local development infrastructure
```

## Local development

1. Copy `.env.example` to `.env`.
2. Run `pnpm infra:up`.
3. Follow `apps/api/README.md` to start the API and workers.
4. Run `pnpm install`, then `pnpm dev:web`.

The current skeleton exposes:

- Web UI: `http://localhost:5173`
- API health check: `http://localhost:8000/api/health/`

The target product runs the React UI inside Electron. The Django API remains a
separately deployed cloud service; it is not bundled into the desktop app.

### Desktop (Electron)

The Electron thin host lives in `apps/desktop` (main + preload + shared IPC
contract). It loads the `apps/web` renderer: the Vite dev server in development
and the packaged renderer build in production.

```bash
pnpm dev:desktop        # start the Vite renderer + Electron together
pnpm build:desktop      # build renderer + compile main/preload bundles
pnpm dist:desktop       # produce a Windows NSIS installer (electron-builder)
```

The renderer talks to the desktop only through the typed, allow-listed
`window.mentoraDesktop` bridge (see `apps/desktop/src/shared/desktopApi.ts`).
Node.js, the filesystem, and auth tokens are never exposed to the renderer.
Architecture and security baseline:
[desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md)
and [ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md).
Implementation status and verification notes:
[implementation-log.md](docs/project-management/implementation-log.md).

See [end-to-end-implementation-plan.md](docs/architecture/end-to-end-implementation-plan.md)
for the product architecture and implementation roadmap.

四人团队的职责分工、交付路线、协作规则和当前迭代任务见
[团队工程手册](docs/project-management/README.md)。

See [scope-versioning-design.md](docs/architecture/scope-versioning-design.md)
for source versions, course scope revisions, incremental impact analysis,
activation, and rollback semantics.

The corresponding proposed decision record is
[ADR-0001](docs/architecture/adr/0001-course-scope-versioning.md).

Question banks, AI-generated item review, assessment forms, scoring, and
mastery evidence are specified in
[assessment-item-bank-design.md](docs/architecture/assessment-item-bank-design.md)
and [ADR-0002](docs/architecture/adr/0002-assessment-item-lifecycle.md).

The real-time adaptive generation and automatic accuracy gate are specified in
[adaptive-ai-question-generation-design.md](docs/architecture/adaptive-ai-question-generation-design.md)
and [ADR-0003](docs/architecture/adr/0003-adaptive-ai-question-validation.md).

Course-profile review, editable learning-plan cards, and atomic course startup
are specified in
[ADR-0004](docs/architecture/adr/0004-profile-plan-confirmation.md).

The Electron process boundary, secure IPC, authentication, file upload, and
desktop release strategy are specified in
[desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md)
and [ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md).

---

# Mentora（中文）

Mentora 是一个 Electron 桌面课程工作区，用于个性化学习。
学习资源存放在可复用的用户库中。每门课程引用一个明确、带版本的知识范围，并拥有自己的学习意图、学习计划、学习事件、评估以及可执行的学习地图。

## 仓库布局

```text
apps/
  desktop/      目标 Electron main/preload 宿主（待实现）
  web/          当前 React/Vite 渲染层
  api/          Django REST API、SSE、Celery 及领域工作流
docs/
  architecture/ 架构与模块边界文档
infra/
  docker/       本地开发基础设施
```

## 本地开发

1. 将 `.env.example` 复制为 `.env`。
2. 运行 `pnpm infra:up`。
3. 参照 `apps/api/README.md` 启动 API 和 worker。
4. 运行 `pnpm install`，然后运行 `pnpm dev:web`。

当前预 Electron 骨架暴露以下入口：

- Web UI：`http://localhost:5173`
- API 健康检查：`http://localhost:8000/api/health/`

目标产品在 Electron 中运行 React UI。Django API 保持为独立部署的云服务，不会打包到桌面应用中。

产品架构与实现路线图详见 [end-to-end-implementation-plan.md](docs/architecture/end-to-end-implementation-plan.md)。

资源版本、课程范围修订、增量影响分析、激活与回滚语义详见 [scope-versioning-design.md](docs/architecture/scope-versioning-design.md)。

相应的提议决策记录为 [ADR-0001](docs/architecture/adr/0001-course-scope-versioning.md)。

题库、AI 生成题目审核、评估表单、评分与掌握度证据详见 [assessment-item-bank-design.md](docs/architecture/assessment-item-bank-design.md) 和 [ADR-0002](docs/architecture/adr/0002-assessment-item-lifecycle.md)。

实时自适应生成与自动准确率门槛详见 [adaptive-ai-question-generation-design.md](docs/architecture/adaptive-ai-question-generation-design.md) 和 [ADR-0003](docs/architecture/adr/0003-adaptive-ai-question-validation.md)。

课程档案审查、可编辑学习计划卡片和原子化课程启动详见 [ADR-0004](docs/architecture/adr/0004-profile-plan-confirmation.md)。

Electron 进程边界、安全 IPC、认证、文件上传与桌面发布策略详见 [desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md) 和 [ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md)。
