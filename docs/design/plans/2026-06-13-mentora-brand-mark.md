# Mentora 品牌标识实现计划

**目标：** 用已批准的 M+书签标识替换通用毕业帽图标，并在仓库贡献指南中确立中文 Conventional Commit 格式。

**架构：** 在现有 shell 模块内新增单一 SVG 组件，保持标识代码原生。保留既有品牌链接、尺寸、色板与无障碍契约。在贡献指南中记录 commit 类型及标题/正文结构要求。

**技术栈：** React、TypeScript、内联 SVG、CSS、Git。

---

### 任务 1：实现品牌标识

**涉及文件：**
- 修改：`apps/web/src/components/AppShell.tsx`
- 修改：`apps/web/src/styles.css`

- [ ] 移除 `GraduationCap` 依赖。
- [ ] 添加 `MentoraMark` SVG（M 外轮廓、中轴书签、底部书页线）。
- [ ] 保持现有 25px 容器并校验视觉对齐。

### 任务 2：文档化提交规范

**涉及文件：**
- 修改：`CONTRIBUTING.md`

- [ ] 定义支持的 commit 类型。
- [ ] 要求简短中文标题。
- [ ] 要求空一行后接具体中文改动说明。
- [ ] 提供有效示例。

### 任务 3：验证并提交

**涉及文件：**
- 验证：`apps/web/src/components/AppShell.tsx`
- 验证：`apps/web/src/styles.css`
- 验证：`CONTRIBUTING.md`

- [ ] 运行 `corepack pnpm typecheck:web`。
- [ ] 运行 `corepack pnpm test:web`。
- [ ] 运行 `corepack pnpm build:web`。
- [ ] 在桌面与窄浏览器宽度下检查标识。
- [ ] 使用新格式提交。
