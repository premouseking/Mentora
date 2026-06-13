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
| 主进程 | `src/main/bootstrap.ts` | 单实例锁、`mentora://` Deep Link、生命周期 |
| 主进程 | `src/main/window.ts` | 安全基线（sandbox、CSP、导航拦截） |
| 主进程 | `src/main/auth.ts` | safeStorage + PKCE 登录 + 单飞刷新（待后端对接） |
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
- 开发态加载 `apps/web` Vite（`http://localhost:5173`）；打包态加载 `../web/dist` → `resources/renderer`
- `README.md`、`.env.example` 补充桌面开发说明（`MENTORA_API_BASE_URL`）

### 影响范围

- **WH**：Main/Preload 骨架已就绪；后续 P1 上传链路应通过 `window.mentoraDesktop.files` / `uploads` / `api` 接入，不再在 renderer 直接使用浏览器文件路径
- **LBZ**：renderer 可通过 `window.mentoraDesktop` 类型契约集成；`apps/web` 暂不重命名，仍作 renderer
- **LH / LWJ**：无直接代码影响；上传与 SSE 仍走云端 Django
- **阶段一风险**：「Electron Host 尚未实现」已降级为「骨架已落地，待与上传 API 联调验收」

### 尚未完成 / 已知限制

- 登录、上传、SSE 等 IPC 已实现骨架，**尚未与 Django 真实端点联调**
- 文档 §12 要求的 IPC/SSE/Deep Link 单测与 Playwright Electron E2E **未编写**
- Windows 代码签名与生产更新 feed 仍为占位配置（`electron-builder.yml` → `updates.example.com`）
- `pnpm dev:desktop` 未在本机做 GUI 冒烟（需人工启动验证窗口）
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
