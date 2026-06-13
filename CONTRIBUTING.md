# Mentora 贡献指南

Cursor Agent 自动读取 `.cursor/rules/`。本文件面向人类协作者。

## AI 协作者（Cursor Agent）

Git 写操作（`add`、`commit`、`push`、`merge` 等）默认由 AI 先说明计划并给出命令；开发者在当前对话明确授权后，AI 可代为执行。AI 在执行前应：

1. 只读检查仓库（`status`、`diff`、`log` 等）
2. 起草符合下方格式的 commit message
3. 说明拟执行命令、分支流向、文件范围与风险

若开发者未授权，AI 只给出可复制命令，由开发者在本地终端执行。高风险操作（强制推送、`reset --hard`、丢弃工作区改动等）必须单独确认。细则见 `.cursor/rules/git-rules.mdc`；Shell 确认与拦截见 `.cursor/rules/shell-file-safety.mdc` 与 `.cursor/hooks/`。

**语言约定：** 仓库文档（`README.md`、`docs/`、`apps/*/README.md` 等）正文使用简体中文；代码标识符、命令、环境变量名、协议字段等专有名词可保留英文。

## 开始任务前

1. 阅读 `README.md`。
2. 阅读 `docs/architecture/` 下与任务有关的文档。
3. 阅读 `docs/project-management/team-charter.md`。
4. 使用 `docs/project-management/templates/task-template.md` 创建任务。
5. 确认任务满足「就绪定义」（Definition of Ready）。

## 分支命名

```text
feat/<task-id>-<description>
fix/<task-id>-<description>
docs/<task-id>-<description>
```

功能开发中不要混入无关重构。

## Commit

```text
<type>: <简短中文说明>

<一段具体的中文改动说明>
```

标题与正文之间必须空一行。

常用类型：`feat` `fix` `refactor` `docs` `test` `style` `perf` `chore` `ci` `revert`

示例：

```text
feat: 实现阶段总结与方案调整页面

新增 StageSummaryPage 及相关组件，串联课程工作台与学习任务入口。
```

## 共享契约与安全

修改 IPC、REST、Event、Schema 时须同 PR 更新文档、兼容性说明与契约测试。

禁止提交或记录：Token、预签名 URL、私有资料正文、隐藏测评答案、本地绝对路径。

## 验证命令

渲染层（`apps/web`）：

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
```

桌面端（`apps/desktop`）：

```powershell
pnpm --dir apps/desktop typecheck
pnpm --dir apps/desktop build:bundle
pnpm dev:desktop   # Vite HMR + nodemon 重启 Electron（改 main/preload 时）
```

API（在 `apps/api` 目录下；首次须按 [apps/api/README.md](apps/api/README.md) 创建环境并 `pip install -e ".[dev]"`）：

```powershell
pytest
ruff check .
```

所有变更：

```powershell
git diff --check
```
