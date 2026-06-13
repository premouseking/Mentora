# Electron GUI Smoke 验收设计

## 目标

让现有 Electron thin host 从“能够编译”推进到“能够在 Windows 开发环境稳定启动并完成基础 GUI 验收”，同时提供一条可重复执行的 smoke 命令。

本阶段不接入真实登录、上传、SSE 或自动更新服务，也不替代后续完整 Playwright Electron E2E。

## 当前基线

- `apps/desktop` 已包含 main、preload、shared IPC 契约及 electron-builder 配置。
- `pnpm typecheck:desktop` 与 `pnpm build:desktop` 已通过。
- `pnpm dev:desktop` 已通过 GUI 冒烟与人工验收。
- Renderer 由 `apps/web` 提供，开发态通过 Vite `http://localhost:5173` 加载；`tsup --watch` + `nodemon` 在主/preload 变更时重启 Electron。

## 方案

采用“开发态人工 GUI 验收 + 自动化最小 smoke 脚本”。

人工验收用于确认真实窗口渲染、窗口操作和视觉错误；自动化 smoke 用于持续验证 Electron 能启动、preload bridge 能注入、renderer 能加载，并能在超时后可靠清理进程。

暂不直接建设完整 Playwright E2E。完整 E2E 需要稳定的测试数据、登录替身和跨进程 fixture，本阶段只覆盖 Electron 宿主基线。

## 验收范围

### 启动与加载

- `pnpm dev:desktop` 能同时启动 Vite、main/preload watch（`tsup`）、Electron（经 `nodemon` 监听编译产物自动重启）。
- 主窗口在限定时间内显示，不停留在白屏或加载失败页。
- Renderer 页面无导致应用不可用的 uncaught exception。
- DevTools 可在开发态使用，但自动 smoke 不依赖人工操作 DevTools。

### Preload 与安全边界

- `window.mentoraDesktop` 已注入。
- `window.mentoraDesktop.app.getInfo()` 能返回版本、平台和 packaged 状态。
- Renderer 中 `window.require` 不可用。
- Renderer 中不暴露 Node.js 文件系统能力或 Electron `ipcRenderer`。

### 窗口生命周期

- 主窗口可最小化、最大化或还原。
- 主窗口关闭后，Windows 开发态 Electron 进程正常退出。
- smoke 成功、失败或超时后都清理其启动的子进程，不遗留 Vite 或 Electron 进程。

### 导航基线

- Renderer 主页面允许正常加载和刷新。
- 非允许来源的窗口内导航被阻止。
- HTTP/HTTPS 新窗口请求不在 Electron 内创建不受控窗口。

## 自动化结构

新增一个面向开发环境的 Electron smoke 脚本，由脚本自行启动 Vite、等待端口、启动 Electron，并通过 Electron automation API 检查窗口与 preload bridge。

脚本职责保持单一：

1. 启动 renderer 开发服务器。
2. 等待 renderer 可访问。
3. 启动 Electron。
4. 等待首个 BrowserWindow。
5. 执行 renderer 与 preload 断言。
6. 关闭应用并清理子进程。

根目录提供统一命令，避免依赖开发者手动拼接启动步骤。

## 错误处理

- Vite 未在超时时间内就绪时，输出明确阶段和端口信息。
- Electron 未创建窗口时，输出 main process 的标准输出与错误输出。
- Renderer 加载失败或 preload API 缺失时，smoke 以非零状态退出。
- 所有退出路径都执行进程清理。
- 不吞掉 Electron main process 的启动错误。

## 测试与验证

本阶段完成后执行：

```powershell
pnpm typecheck:desktop
pnpm build:desktop
pnpm smoke:desktop
```

同时进行一次真实 GUI 验收：

```powershell
pnpm dev:desktop
```

人工确认窗口显示、页面可交互、窗口控制正常、关闭后进程退出。

## 完成标准

- 三条自动化命令全部通过。
- Electron 窗口在本机 Windows 环境成功显示。
- `window.mentoraDesktop.app.getInfo()` 可调用。
- Renderer 无 Node.js 直接访问能力。
- 关闭应用后无本轮启动遗留进程。
- 验收结果写入 `docs/project-management/implementation-log.md`。

