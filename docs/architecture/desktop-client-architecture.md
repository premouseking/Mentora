# Mentora Electron 桌面客户端架构

> 状态：骨架已落地（2026-06-13），待与上传/认证/SSE 后端联调及 §12 验收。
> 首发平台：Windows 10/11 x64。
> 产品形态：Electron 薄客户端 + 云端 Django 服务。

## 1. 决策摘要

Mentora 的主要用户入口改为 Electron 桌面客户端。客户端提供课程工作台、资料选择、
本地文件上传、阅读定位、通知和系统集成；课程、资料版本、解析、检索、AI、计划、
评测和学习状态仍由云端服务负责。

```text
Electron Main
  -> Window / Deep Link / File / Upload / Notification / Updater
  -> Authenticated API and SSE bridge

Preload
  -> typed, allow-listed contextBridge API

React Renderer
  -> course workspace and learning UI
  -> no Node.js, filesystem or token access

Cloud
  -> Django + Celery + PostgreSQL + Redis + Object Storage
```

首期要求联网，不将 Django、PostgreSQL、Redis、Celery、OCR 或模型运行时打包进客户端。

## 2. 从 Lightest 提取的经验

参考 Lightest 的实际 Electron 实现，采用以下经验：

- `main.ts` 只负责崩溃保护和启动，业务初始化放入可诊断的 bootstrap；
- `main/` 按窗口、认证、文件、网络、更新和生命周期拆分；
- `main/ipc/` 按能力域注册 `ipcMain.handle`，不建立一个万能 IPC；
- preload 是 renderer 的唯一桌面能力边界；
- 普通 HTTP、SSE、取消和上传由主进程桥接，renderer 不持有长期令牌；
- 开发态加载 Vite URL，打包态加载本地 renderer 产物；
- 使用单实例锁、Deep Link、窗口状态恢复和外部链接限制；
- 自动更新区分开发、unpacked 和正式安装包；
- 发布元数据必须在安装包上传完成后最后发布；
- 打包前后执行路径、资源和安装包 Smoke Test。

不复用：

- Agent、终端、SSH、Git 工具链和远程运行时；
- Computer Use、Office Add-in 和内置浏览器；
- 大量原生 Node 模块和随包工具链；
- Lightest 的业务 IPC 名称、认证协议和状态模型。

## 3. 进程职责

### 3.1 Main Process

主进程负责：

- 应用单实例、窗口创建、缩放和状态恢复；
- 系统浏览器登录和 `mentora://` Deep Link；
- 安全保存 Refresh Token；
- 访问 Mentora API、刷新 Access Token 和桥接 SSE；
- 文件选择、类型初检、SHA-256、分片读取和直传对象存储；
- 打开系统文件夹、外部链接和系统通知；
- 自动更新、崩溃日志和基础诊断；
- 阻止 renderer 任意导航、任意文件访问和任意网络代理。

主进程不负责：

- 课程、画像、计划、作用域或掌握度业务规则；
- PDF/OCR/Office/视频正式解析；
- RAG、Embedding 或模型调用；
- 保存云端领域对象的第二份事实源。

### 3.2 Preload

preload 通过 `contextBridge` 暴露小型能力：

```text
window.mentoraDesktop
  app
  auth
  api
  events
  files
  uploads
  shell
  notifications
  updater
  window
```

约束：

- 所有方法使用共享 TypeScript DTO；
- 参数在 preload 和 main 两侧都做 Schema 校验；
- 不暴露 `ipcRenderer`、文件系统模块、环境变量或任意 channel；
- 事件订阅必须返回 unsubscribe；
- IPC channel 使用 `mentora:<domain>:<action>` 命名。

### 3.3 Renderer

renderer 沿用 React、TypeScript 和 Vite，负责：

- 课程创建、画像确认和学习路径编辑；
- 课程工作台、学习、提问、练习和知识地图；
- 资源库、上传队列和处理进度；
- PDF、PPT、Word、视频和网页引用展示；
- React Query 缓存和功能内临时交互状态。

renderer 不能：

- 使用 Node.js API；
- 读取本地任意路径；
- 保存 Access Token 或 Refresh Token；
- 直接连接对象存储或外部模型、搜索提供方；
- 绕过主进程 API Bridge 访问 Mentora 后端。

## 4. 安全基线

`BrowserWindow.webPreferences`：

```text
nodeIntegration: false
contextIsolation: true
sandbox: true
webSecurity: true
preload: packaged/dev resolved path
```

必须实施：

- 严格 CSP，不允许 `unsafe-eval`；
- `will-navigate` 只允许开发服务器或打包 renderer；
- `setWindowOpenHandler` 默认拒绝，新链接经确认后交给系统浏览器；
- API Bridge 只接受相对 API path，不接受 renderer 提供任意 URL；
- 文件能力使用主进程生成的临时 `file_token`，不向 renderer 暴露通用读文件接口；
- 上传前检查扩展名、MIME、魔数、大小并计算 SHA-256；
- Refresh Token 使用 Electron `safeStorage` 加密后保存；
- 日志不记录令牌、原始学习回答、文件正文和预签名 URL；
- 生产包启用代码签名，更新只接受受信发布源。

## 5. 网络与认证

### 5.1 API Bridge

```text
Renderer
  -> preload api.request()
  -> IPC
  -> Main Process authenticated fetch
  -> Django API
```

主进程统一处理：

- API Base URL；
- Access Token 注入；
- 401 后单飞刷新令牌；
- 请求超时、取消和错误归一化；
- Client Version、Device ID 和 Request ID；
- 网络离线状态。

不能实现通用开放代理。请求 path 必须匹配 Mentora API allowlist，method、body 大小和
response type 都有限制。

### 5.2 SSE Bridge

```text
events.open({path, lastEventId})
  -> 返回 stream_id
  -> main fetch ReadableStream
  -> stream-head / stream-event / stream-error / stream-end
  -> events.abort(stream_id)
```

服务端 `RuntimeEvent` 仍是可恢复事件。IPC 只负责传输，断线后以 `Last-Event-ID` 续传；
回放过期时重新读取 REST 快照。

### 5.3 桌面登录

```text
客户端生成 state + PKCE
  -> 系统浏览器打开登录页
  -> 登录成功跳转 mentora://auth/callback
  -> 单实例主进程接收 Deep Link
  -> 校验 state 并交换一次性 code
  -> safeStorage 保存 Refresh Token
```

不在 renderer 或 URL 中传递长期令牌。自定义协议同时支持：

- `mentora://auth/callback`；
- `mentora://course/{courseId}`；
- `mentora://task/{taskId}`。

## 6. 文件选择与上传

### 6.1 文件能力

```text
files.pick()
  -> Main dialog.showOpenDialog
  -> 返回 file_token + name + size + mime
```

`file_token` 绑定绝对路径、窗口、用户会话和短期有效时间。renderer 不能提交任意本地
路径要求主进程读取。

### 6.2 上传链路

```text
Renderer 请求创建上传
  -> Django 返回 upload_id 和分片预签名信息
  -> Main Process 从 file_token 对应路径流式读取
  -> 直接 PUT 到对象存储
  -> 上报进度
  -> Django complete 校验 SHA-256 和对象元数据
```

大文件不以完整 base64 内容穿过 IPC。首期支持上传进行中的取消和应用内重试；应用关闭
后的跨启动断点续传后置，避免为本地队列引入 SQLite/native module。

云端仍执行 ClamAV、魔数复核、页数/时长限制和隔离解析。客户端检查只用于尽早反馈，
不能替代服务端安全检查。

## 7. 本地状态与离线边界

首期仅保存：

- 窗口位置、主题、缩放和非敏感偏好；
- 加密 Refresh Token；
- 安装 ID、最近账户和更新检查时间；
- 崩溃与启动诊断日志。

课程、计划、学习事件、题目、掌握度和资料元数据均以服务端为事实源。网络断开时允许：

- 查看当前界面已经加载的只读数据；
- 编辑尚未提交的表单；
- 等待网络恢复后由用户重试。

首期不承诺离线学习、离线检索或离线 AI。后续若立项离线阅读，再单独设计加密缓存、
淘汰策略、同步冲突和本地数据库。

## 8. 窗口与生命周期

- 使用 `requestSingleInstanceLock`；
- 第二实例将 Deep Link 或文件打开请求转交主实例；
- Windows 关闭窗口默认退出应用；
- 有进行中上传时提示继续等待或取消并退出；
- 画像和路径草稿持续保存到服务端，不依赖关闭前一次性 flush；
- renderer 崩溃后可重载并从服务端恢复；
- 主进程启动失败必须在业务 import 前注册日志和崩溃处理；
- 开发态和生产态分别解析 preload、renderer 和资源路径。

首期不实现常驻托盘和关闭后后台上传。

## 9. 通知和系统集成

- 后台解析、计划生成和题目生成完成后可发送系统通知；
- 点击通知通过内部路由打开对应课程或任务；
- 外部链接默认交给系统浏览器；
- “在文件夹中显示”只用于用户主动下载的文件；
- 下载文件通过系统保存对话框选择位置；
- 后续可以增加全局快捷键和协议文件关联，首期不做。

## 10. 打包、更新与发布

采用：

- Electron；
- `electron-builder`；
- Windows NSIS 安装包；
- `electron-updater`；
- 对象存储或 CDN 上的 generic update feed。

更新策略：

- 开发态和 unpacked 目录不检查更新；
- 正式安装包启动后延迟检查；
- 可后台下载，但不得退出时静默安装；
- 下载完成后由用户点击“重启并安装”；
- renderer 只展示主进程广播的更新状态；
- 发布时先上传安装包和 blockmap，最后发布 `latest.yml`；
- 正式外发前必须完成 Windows 代码签名。

首期发布顺序：

1. `build renderer`；
2. 编译 main/preload；
3. 检查运行时路径和 CSP；
4. `electron-builder --dir`；
5. unpacked Smoke Test；
6. 生成 NSIS；
7. 安装、启动、登录、上传和更新 Smoke Test；
8. 上传二进制；
9. 最后上传更新元数据。

## 11. 目标目录

```text
apps/
  desktop/
    src/
      main/
        bootstrap.ts
        window.ts
        auth.ts
        apiClient.ts
        eventStreams.ts
        uploads.ts
        updater.ts
        ipc/
      preload/
        index.ts
      shared/
        desktopApi.ts
        schemas.ts
    electron-builder.yml
    package.json
  web/
    src/                 暂作为 renderer，后续可重命名为 renderer
  api/
```

迁移初期允许 `apps/desktop` 直接加载 `apps/web` 的 Vite 页面，避免先做无价值目录搬迁。
当 Electron 主链路稳定后，再决定是否将 `apps/web` 重命名为 `apps/renderer`。

## 12. 测试与验收

### 12.1 自动测试

- main/preload 共享 DTO 和 Schema 单元测试；
- IPC allowlist、参数验证和错误映射测试；
- API 401 刷新并发测试；
- SSE 分片、取消、断线续传和 renderer 销毁测试；
- 文件 token 越权、过期和窗口隔离测试；
- 分片上传取消、失败重试和 SHA-256 测试；
- Deep Link state/PKCE 测试；
- 更新状态机测试；
- Playwright Electron E2E。

### 12.2 首期验收

1. renderer 无法访问 `require`、`process.env` 和任意本地文件。
2. 未登录用户能通过系统浏览器完成登录并回到同一客户端。
3. 用户能选择大 PDF，主进程流式上传且 IPC 内存不随文件大小线性增长。
4. 解析和问答 SSE 可取消、断线恢复，renderer 重载后能读取最终状态。
5. 外部链接、导航和新窗口不能绕过安全策略。
6. 同时启动两个实例只保留主实例。
7. unpacked 构建不误报可更新；正式安装版可完成检查、下载和用户确认安装。
8. renderer 崩溃或应用重启后，云端课程、画像、计划和任务状态不丢失。

## 13. 当前不做

- 不在客户端内置 Django、Celery、Redis、PostgreSQL 或对象存储；
- 不在 renderer 直接请求模型、搜索提供方或对象存储；
- 不支持任意 IPC channel、任意 URL 请求和任意路径读取；
- 不引入终端、SSH、Git、Computer Use 或本地 Agent Runtime；
- 不为首期离线能力引入 `better-sqlite3` 等原生模块；
- 不实现内置通用浏览器、插件系统和多窗口工作区；
- 不在未签名、未验证的安装包上启用生产自动更新。
