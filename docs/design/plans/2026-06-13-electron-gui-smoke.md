# Electron GUI Smoke 实现计划

> **面向 Agent 协作者：** 建议配合 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步执行。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 为 Mentora Electron 开发环境增加可重复执行的 GUI smoke 验收，并在本机完成真实窗口启动检查。

**架构：** 使用 Playwright 的 Electron 自动化启动现有编译产物，由独立 smoke 脚本启动和清理 Vite 子进程。进程树清理逻辑放入可单测辅助模块；集成 smoke 检查窗口、renderer、preload 桥接与 Node 隔离。

**技术栈：** Electron 33、Playwright、Node.js test runner、pnpm、TypeScript/JavaScript

---

## 文件结构

- 新建 `apps/desktop/scripts/process-tree.mjs`：跨平台终止 smoke 启动的子进程树。
- 新建 `apps/desktop/scripts/process-tree.test.mjs`：验证进程终止命令与无效进程处理。
- 新建 `apps/desktop/scripts/smoke.mjs`：启动 Vite 和 Electron，执行 GUI/preload/安全断言并清理。
- 修改 `apps/desktop/package.json`：增加 Playwright、单测和 smoke 命令。
- 修改根 `package.json`：暴露统一 `test:desktop` 与 `smoke:desktop` 命令。
- 修改 `docs/project-management/implementation-log.md`：记录实际 GUI 验收结果。
- 保留 `docs/design/specs/2026-06-13-electron-gui-smoke-design.md`：与实现一并提交。

### 任务 1：进程树清理辅助模块

**涉及文件：**
- 新建：`apps/desktop/scripts/process-tree.test.mjs`
- 新建：`apps/desktop/scripts/process-tree.mjs`
- 修改：`apps/desktop/package.json`

- [ ] **步骤 1：编写失败测试**

测试 Windows 使用 `taskkill /PID <pid> /T /F`，非 Windows 使用负 PID 发送 `SIGTERM`，并忽略已经退出的子进程。

- [ ] **步骤 2：运行测试并确认因模块缺失而失败**

运行：`pnpm --dir apps/desktop test`

预期：失败，提示无法导入 `process-tree.mjs`。

- [ ] **步骤 3：实现最小进程树清理模块**

模块接受可注入的 `platform`、`spawnSync` 和 `kill`，生产调用使用 Node 默认实现，测试不启动真实进程。

- [ ] **步骤 4：运行测试并确认通过**

运行：`pnpm --dir apps/desktop test`

预期：通过，全部进程清理单测通过。

### 任务 2：Electron GUI 集成 smoke

**涉及文件：**
- 新建：`apps/desktop/scripts/smoke.mjs`
- 修改：`apps/desktop/package.json`
- 修改：`package.json`
- 修改：`pnpm-lock.yaml`

- [ ] **步骤 1：添加 smoke 命令并确认因脚本缺失而失败**

运行：`pnpm smoke:desktop`

预期：失败，提示 `scripts/smoke.mjs` 不存在。

- [ ] **步骤 2：安装 Playwright 依赖**

运行：`pnpm --filter @mentora/desktop add -D playwright`

预期：`apps/desktop/package.json` 与 `pnpm-lock.yaml` 更新。

- [ ] **步骤 3：实现 smoke 脚本**

脚本执行以下顺序：

1. 启动 `pnpm --dir ../web dev --host 127.0.0.1`。
2. 轮询 `http://127.0.0.1:5173`，超时后输出 Vite 日志。
3. 通过 Playwright `_electron.launch()` 启动 Electron，并设置 `MENTORA_DEV_SERVER_URL`。
4. 等待首个窗口和 `domcontentloaded`。
5. 断言页面 URL、非空标题、`window.mentoraDesktop`、`app.getInfo()`、`window.require` 和 `window.process`。
6. 调用窗口最小化和最大化桥接，确认 IPC 可执行。
7. 关闭 Electron，并在 `finally` 中清理 Electron 与 Vite 进程。

- [ ] **步骤 4：构建并运行集成 smoke**

运行：

```powershell
pnpm build:desktop
pnpm smoke:desktop
```

预期：输出各阶段 `PASS`，进程退出码为 0。

### 任务 3：真实 GUI 验收与记录

**涉及文件：**
- 修改：`docs/project-management/implementation-log.md`

- [ ] **步骤 1：启动真实开发窗口**

运行：`pnpm dev:desktop`

预期：Mentora 主窗口显示 renderer 页面；Vite 提供 renderer HMR；改 main/preload 后 nodemon 自动重启 Electron。

- [ ] **步骤 2：检查真实窗口**

确认页面可见、无白屏、窗口可最小化/还原/关闭，关闭后本轮 Electron 与 Vite 进程退出。

- [ ] **步骤 3：写入验收记录**

记录日期、命令、自动 smoke 结果、人工窗口结果和仍未覆盖的登录/上传/SSE 范围。

### 任务 4：完整回归与功能提交

**涉及文件：**
- 验证上述全部文件

- [ ] **步骤 1：运行完整验证**

运行：

```powershell
pnpm --dir apps/desktop test
pnpm typecheck:desktop
pnpm build:desktop
pnpm smoke:desktop
git diff --check
```

预期：所有命令退出码为 0。

- [ ] **步骤 2：检查改动范围**

运行：`git diff -- apps/desktop package.json pnpm-lock.yaml docs/design/specs/2026-06-13-electron-gui-smoke-design.md docs/design/plans/2026-06-13-electron-gui-smoke.md docs/project-management/implementation-log.md`

预期：仅包含 Electron GUI smoke 相关改动。

- [ ] **步骤 3：创建一个符合规范的功能提交**

提交标题与正文：

```text
test: 增加 Electron GUI 冒烟验收

新增可重复执行的 Electron 窗口、preload 桥接与安全边界 smoke 检查，补充进程清理测试和本机 GUI 验收记录，并将对应设计与实施计划一并纳入提交。
```
