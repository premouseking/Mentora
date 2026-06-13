# Mentora 桌面标题栏设计

## 目标

用 Mentora 自有的单一桌面标题栏，取代重复的 Electron 系统 chrome 与 renderer 模拟窗口栏。

## 窗口行为

- Electron 窗口为无边框（frameless）。
- 移除 Electron 默认应用菜单。
- renderer 标题栏是唯一可见的标题栏。
- 标题栏空白区域可拖拽，支持平台窗口拖动行为。
- 交互控件排除在 drag 区域之外。
- 最小化、最大化/还原、关闭使用既有 allowlist 桌面 IPC 桥接。
- 标题栏在已登录、建课、加载与认证页面均存在。

## 布局行为

- 应用填满 Electron 客户区。
- renderer 不绘制带外边距、圆角或页面阴影的「浏览器式浮动画布」。
- `html`、`body`、`#root` 与应用 shell 固定于视口，不产生文档级滚动条。
- 超出可用空间的内容仅在明确的内容面板内滚动（如课程列表、文件浏览、阅读器、测验、AI 面板）。

## 验收

- Electron smoke 测试确认 `frame: false` 且无应用菜单。
- renderer 暴露且仅暴露一条标题栏。
- 标题栏包含 drag 与 no-drag 区域。
- 文档不溢出 Electron 视口。
- 桌面测试、类型检查与生产构建通过。
