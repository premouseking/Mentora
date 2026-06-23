# Mentora

Mentora 是一个 Electron 桌面课程工作区，用于个性化学习。
学习资源存放在可复用的用户库中。每门课程引用一个明确、带版本的知识范围，并拥有自己的学习意图、学习计划、学习事件、评估以及可执行的学习地图。

## 仓库布局

```text
apps/
  desktop/      Electron 薄宿主（main + preload + 共享 IPC）
  web/          React/Vite 渲染层（HashRouter；由 desktop 加载）
  api/          Django REST API、SSE、Celery 及领域工作流
docs/
  architecture/   架构设计、ADR、模块边界
  design/         产品 UX、规格、实现计划、mockup
  project-management/  团队流程、backlog、模板、实现日志
infra/
  docker/       本地开发基础设施
```

## 协作

- [文档索引](docs/README.md)
- [团队工程手册](docs/project-management/README.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)（Cursor 规则见 `.cursor/rules/`）

## 本地开发

详见 [本地基础设施指南](docs/dev/local-infrastructure.md)。

1. 将 `.env.example` 复制为 `.env`。
2. 运行 `pnpm infra:up`。
3. 参照 `apps/api/README.md` 启动 API：`pnpm api:migrate`、`pnpm api:seed`。
4. 运行 `pnpm install`，然后运行 `pnpm dev:web` 或 `pnpm dev:desktop`。

当前骨架暴露以下入口：

- Web UI：`http://localhost:5173`
- API 健康检查：`http://localhost:8000/api/health/`

目标产品在 Electron 中运行 React UI。Django API 保持为独立部署的云服务，不会打包到桌面应用中。

### 桌面端（Electron）

Electron 薄宿主位于 `apps/desktop`（main + preload + 共享 IPC 契约）。开发态通过 Vite `http://localhost:5173` 加载 `apps/web` renderer（HMR）；打包态加载 `../web/dist`。主进程/preload 由 `tsup --watch` 编译，`nodemon` 在产物变更时自动重启 Electron。renderer 使用 `HashRouter`，保证打包后 `file://` 子路由稳定。

```bash
pnpm dev:desktop        # 同时启动 Vite、main/preload watch 与 Electron
pnpm build:desktop      # 构建 renderer 并编译 main/preload
pnpm dist:desktop       # 生成 Windows NSIS 安装包
```

开发态流程（对齐 LighTest 桌面模式）：

- **Renderer（`apps/web`）**：Vite dev server 监听 `http://localhost:5173`；Electron 经 `MENTORA_DEV_SERVER_URL` 加载以启用 HMR。
- **Main/preload（`apps/desktop`）**：`tsup --watch` 重建产物；`nodemon` 监听 `dist/main` 与 `dist/preload` 变更并重启 Electron。
- **路由**：renderer 使用 `HashRouter`，避免打包态 `file://` 子路由刷新白屏。

Renderer 仅通过类型化、allowlist 约束的 `window.mentoraDesktop` 桥接与桌面通信（见 `apps/desktop/src/shared/desktopApi.ts`）。Node.js、文件系统与认证 Token 不会暴露给 renderer。

架构与安全基线：[desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md)、[ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md)。实现状态与验收记录：[implementation-log.md](docs/project-management/implementation-log.md)。

四人团队的职责分工、交付路线、协作规则和当前迭代任务见 [团队工程手册](docs/project-management/README.md)。

产品架构与实现路线图详见 [end-to-end-implementation-plan.md](docs/architecture/end-to-end-implementation-plan.md)。

资源版本、课程范围修订、增量影响分析、激活与回滚语义详见 [scope-versioning-design.md](docs/architecture/scope-versioning-design.md)。相应的提议决策记录为 [ADR-0001](docs/architecture/adr/0001-course-scope-versioning.md)。

题库、AI 生成题目审核、评估表单、评分与掌握度证据详见 [assessment-item-bank-design.md](docs/architecture/assessment-item-bank-design.md) 和 [ADR-0002](docs/architecture/adr/0002-assessment-item-lifecycle.md)。

实时自适应生成与自动准确率门槛详见 [adaptive-ai-question-generation-design.md](docs/architecture/adaptive-ai-question-generation-design.md) 和 [ADR-0003](docs/architecture/adr/0003-adaptive-ai-question-validation.md)。

课程档案审查、可编辑学习计划卡片和原子化课程启动详见 [ADR-0004](docs/architecture/adr/0004-profile-plan-confirmation.md)。

Electron 进程边界、安全 IPC、认证、文件上传与桌面发布策略详见 [desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md) 和 [ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md)。
