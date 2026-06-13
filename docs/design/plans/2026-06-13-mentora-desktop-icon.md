# Mentora 桌面图标实现计划

> **面向 Agent 协作者：** 建议配合 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步执行。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 在开发与 Windows 打包产物中，用已批准的 Mentora B 版图标替换 Electron 默认图标。

**架构：** 在 `apps/desktop/build` 保留单一 SVG 源；用确定性 Node 脚本生成 PNG 与多尺寸 ICO；主进程配置模块集中解析开发态图标路径。electron-builder 打包复用同一套生成产物。

**技术栈：** Electron、TypeScript、Node.js、Playwright、electron-builder。

---

### 任务 1：生成桌面图标资源

**涉及文件：**
- 新建：`apps/desktop/build/icon.svg`
- 新建：`apps/desktop/scripts/generate-icons.mjs`
- 新建：`apps/desktop/build/icon.png`
- 新建：`apps/desktop/build/icon-dev.png`
- 新建：`apps/desktop/build/icon.ico`
- 修改：`apps/desktop/package.json`

- [x] 添加已批准的粗线条 `M + 书签` SVG（`#123f37` 底、白色描边）。
- [x] 添加确定性生成脚本：渲染 PNG 尺寸并将帧打包为 ICO。
- [x] 添加 `icons:generate` 并执行。
- [x] 校验 PNG 尺寸与 ICO 帧大小。

### 任务 2：接入开发态窗口图标

**涉及文件：**
- 新建：`apps/desktop/scripts/desktop-icon-config.test.mjs`
- 修改：`apps/desktop/src/main/config.ts`
- 修改：`apps/desktop/src/main/window.ts`

- [x] 添加失败态源码级测试，要求存在 `resolveWindowIconPath()` 与 `BrowserWindow.icon`。
- [x] 运行测试并确认因尚未接入图标而失败。
- [x] 实现 `resolveWindowIconPath()`（Windows → `icon.ico`，其他平台 → `icon-dev.png`）。
- [x] 经 `nativeImage.createFromPath` 将解析结果传给 `BrowserWindow`。
- [x] Windows 下设置 `app.setAppUserModelId("com.mentora.desktop")`，使任务栏在开发态也显示自定义图标。
- [x] 重新运行测试并确认通过。

### 任务 3：配置打包并验收

**涉及文件：**
- 修改：`apps/desktop/electron-builder.yml`

- [x] 将 `win.icon` 设为 `build/icon.ico`。
- [x] 运行桌面端测试与类型检查。
- [ ] 运行 Windows 未打包目录产物。本地 electron-builder 因解压签名工具时 Windows 拒绝创建符号链接而受阻。
- [x] 启动 `pnpm dev:desktop`，通过原生 Windows 图标句柄确认 Mentora 图标。
