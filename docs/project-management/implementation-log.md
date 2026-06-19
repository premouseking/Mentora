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
