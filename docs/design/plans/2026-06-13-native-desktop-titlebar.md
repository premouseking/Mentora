# 原生桌面标题栏实现计划

> **面向 Agent 协作者：** 建议配合 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步执行。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 让 Mentora renderer 标题栏成为 Electron 窗口唯一的真实标题栏，并消除文档级滚动。

**架构：** Electron 创建无边框窗口并移除默认菜单。React 渲染可复用标题栏，调用既有类型化窗口 IPC；CSS 定义 drag/no-drag 区域并将应用约束在视口内。

**技术栈：** Electron、React、TypeScript、CSS、Playwright Electron smoke 测试。

---

### 任务 1：添加失败的桌面 chrome 断言

**涉及文件：**
- 修改：`apps/desktop/scripts/smoke.mjs`

- [ ] 断言 BrowserWindow 为无边框且应用菜单为 null。
- [ ] 断言 renderer 中存在唯一标题栏，且含 drag 与 no-drag 区域。
- [ ] 断言文档尺寸不超过视口。
- [ ] 运行 `pnpm smoke:desktop` 并确认新断言失败。

### 任务 2：配置原生窗口

**涉及文件：**
- 修改：`apps/desktop/src/main/window.ts`
- 修改：`apps/desktop/src/main/bootstrap.ts`

- [ ] 以 `frame: false` 创建 BrowserWindow。
- [ ] 在 bootstrap 中移除 Electron 应用菜单。
- [ ] 重新运行桌面 smoke 测试。

### 任务 3：实现可复用 renderer 标题栏

**涉及文件：**
- 新建：`apps/web/src/components/DesktopTitleBar.tsx`
- 修改：`apps/web/src/components/AppShell.tsx`
- 修改：`apps/web/src/pages/AuthPage.tsx`
- 修改：`apps/web/src/components/AuthGate.tsx`
- 修改：`apps/web/src/lib/desktop.ts`
- 修改：`apps/web/src/vite-env.d.ts`

- [ ] 在所有应用路由上渲染同一标题栏。
- [ ] 将窗口按钮连接到类型化 desktop 桥接。
- [ ] 在应用 shell 支持处保留 AI 操作入口。
- [ ] 重新运行类型检查与 smoke 测试。

### 任务 4：将滚动限制在内部面板

**涉及文件：**
- 修改：`apps/web/src/styles.css`

- [ ] 将根元素与 shell 固定到视口。
- [ ] 移除外层画布 margin、圆角与阴影。
- [ ] 标记标题栏 drag 与 no-drag 区域。
- [ ] 保留 `.page-surface` 与既有工作区面板作为内部滚动容器。
- [ ] 在 Electron 最小窗口尺寸与默认尺寸下验证。

### 任务 5：最终验收

- [ ] 运行 `pnpm test:desktop`。
- [ ] 运行 `pnpm typecheck:desktop`。
- [ ] 运行 `pnpm typecheck:web`。
- [ ] 运行 `pnpm build:desktop`。
- [ ] 运行 `pnpm smoke:desktop`。
- [ ] 检查运行中的 Electron 窗口：仅一条标题栏、无文档滚动条。
