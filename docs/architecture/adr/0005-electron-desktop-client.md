# ADR-0005：采用 Electron 薄桌面客户端

- 状态：Proposed（实现骨架：2026-06-13，见 [implementation-log.md](../../project-management/implementation-log.md)）
- 日期：2026-06-12
- 关联设计：`docs/architecture/desktop-client-architecture.md`

## 背景

Mentora 需要频繁选择本地 PDF、PPT、Word 和视频，展示系统通知，并提供稳定的课程
工作台。纯浏览器可以实现大部分业务，但文件访问、系统集成、令牌保护、桌面更新和长期
使用体验受限。将完整后端塞入客户端又会引入数据库、队列、解析器和模型运行时的部署
复杂度。

## 决策

1. 产品主要入口采用 Electron，Windows 10/11 x64 首发。
2. Electron 是薄桌面宿主；Django、Celery、PostgreSQL、Redis、对象存储和 AI 均部署
   在云端。
3. React + TypeScript + Vite 继续作为 renderer 技术栈。
4. renderer 禁用 Node.js，使用 `contextIsolation`、sandbox 和严格 CSP。
5. preload 只通过 typed allowlist 暴露桌面能力，不暴露 `ipcRenderer`。
6. 主进程持有认证令牌，桥接普通 API、SSE、取消和对象存储上传。
7. 本地文件通过临时 `file_token` 授权，主进程按流上传，不以 base64 穿过 IPC。
8. 首期要求联网，不实现离线检索、离线 AI 或本地业务数据库。
9. 使用 `electron-builder + NSIS + electron-updater`；更新下载完成后由用户明确重启
   安装，不在退出时静默安装。
10. 采用 Lightest 的进程边界和发布经验，但不复制其 Agent、终端、SSH、Git、原生
    工具链和业务代码。

## 拒绝方案

### 继续以浏览器 Web 为主要产品

实现成本最低，但本地资料选择、系统通知、令牌隔离和桌面更新体验不符合当前产品方向。

### 客户端内置完整 Python 后端

可以获得离线能力，但需要同时维护 Python、数据库、队列、OCR/Office/媒体依赖和升级
迁移，首期交付与支持成本不可接受。

### renderer 直接使用 Node.js 和文件系统

开发简单，但扩大 XSS 后的本地系统攻击面，无法形成清晰、可审计的桌面能力边界。

### renderer 直接连接云端并保存令牌

减少 IPC，但长期令牌暴露在 renderer，上传、SSE、统一取消和认证刷新也会形成两套
网络实现。

## 结果

正向结果：

- 获得桌面文件、通知、Deep Link 和自动更新能力；
- 云端领域模型和现有 Django 架构保持不变；
- renderer 与本地系统之间有明确安全边界；
- 后续仍可按独立 ADR 增加离线阅读缓存。

代价：

- 需要维护 main、preload、renderer 三层；
- API 和 SSE 需要 IPC Bridge；
- 每个平台需要安装、签名和更新测试；
- 首期没有完整离线学习能力。

## 验收不变量

1. renderer 无法直接访问 Node.js、令牌或任意本地路径。
2. 主进程 API Bridge 不能成为任意 URL 开放代理。
3. 大文件不以完整 base64 内容穿过 IPC。
4. 客户端本地状态不能成为课程、计划和学习记录的唯一事实源。
5. 开发态、unpacked 和正式安装版的更新行为明确区分。
6. 生产更新必须来自受信发布源，并在正式外发前启用代码签名。
