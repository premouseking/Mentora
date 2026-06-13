# Mentora 贡献指南

## 开始任务前

1. 阅读 `README.md`。
2. 阅读 `docs/architecture/` 下与任务有关的文档。
3. 阅读 `docs/project-management/team-charter.md`。
4. 使用 `docs/project-management/templates/task-template.md` 创建任务。
5. 确认任务满足 Definition of Ready。

## 分支命名

使用短生命周期分支：

```text
feat/<task-id>-<description>
fix/<task-id>-<description>
docs/<task-id>-<description>
```

功能开发中不要混入无关重构。

## Commit

优先提交小而可验证的变更，并保证每次提交后分支仍可测试。

提交信息使用以下格式：

```text
<type>: <简短中文说明>

<一段具体的中文改动说明>
```

标题与正文之间必须保留一个空行。标题说明本次提交的目的，正文具体说明修改了什么、
影响哪些模块以及必要的行为变化。

常用类型：

- `feat`：新增用户可见功能；
- `fix`：修复缺陷；
- `refactor`：不改变外部行为的代码重构；
- `docs`：仅修改文档；
- `test`：新增或调整测试；
- `style`：不影响逻辑的格式或视觉样式调整；
- `perf`：性能优化；
- `chore`：构建、依赖或工程维护；
- `ci`：持续集成配置；
- `revert`：撤销已有提交。

示例：

```text
feat: 更新课程阶段总结

新增阶段学习证据、方案调整确认和进入下一阶段的交互，并连接课程主页与学习任务入口。

refactor: 拆分学习任务组件

将原文预览和 AI 辅助面板拆为独立组件，保持现有页面行为不变并降低页面组件复杂度。
```

## 验证命令

Renderer 变更：

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
```

API 变更在 `apps/api` 下运行：

```powershell
pytest
ruff check .
```

所有变更还需要运行：

```powershell
git diff --check
```

如果任务需要更具体的命令，应写入任务和 PR 描述。

## 共享契约

修改 IPC、REST、Runtime Event、Source/Evidence Schema、模型 Schema 或
测评 Schema 时，必须同时提供：

- 生产者和消费者评审；
- 版本或兼容性决策；
- 契约测试；
- 同一 PR 中的文档更新。

## 安全要求

禁止提交或记录：

- Access Token 或 Refresh Token；
- 对象存储签名 URL；
- 测试不需要的私有资料正文；
- Renderer Payload 中的隐藏测评答案；
- 用户机器上的本地绝对路径。

仓库测试 Fixture 必须使用可安全分发的合成资料或公开资料。
