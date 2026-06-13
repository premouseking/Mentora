# Mentora 文档

## 目录结构

```text
docs/
  architecture/          架构设计、ADR、模块边界、端到端方案
  design/                产品 UX、mockup、功能规格与实现计划
    specs/               功能设计规格（评审输入）
    plans/               功能实现计划（按任务拆分）
    mockups/             桌面界面 mockup
    concepts/            概念图
  project-management/    团队流程、backlog、模板、实现日志
    plans/               团队/阶段级工程计划
    project-start/       立项报告模板与交付物
    templates/           任务与决策记录模板
```

Cursor 编码约束见仓库根目录 `.cursor/rules/`；人类协作见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 快速入口

| 我要… | 去看 |
| --- | --- |
| 了解产品架构与 ADR | [architecture/](architecture/) |
| 看 UX 与界面设计 | [design/desktop-product-ux-design.md](design/desktop-product-ux-design.md) |
| 查团队职责与 DoR/DoD | [project-management/team-charter.md](project-management/team-charter.md) |
| 看当前阶段任务 | [project-management/stage-01-backlog.md](project-management/stage-01-backlog.md) |
| 查重要工程改动 | [project-management/implementation-log.md](project-management/implementation-log.md) |

## 文档冲突优先级

1. `architecture/adr/`
2. `architecture/end-to-end-implementation-plan.md`
3. `architecture/module-boundaries.md`
4. `project-management/`（团队工程手册）
5. 当前阶段任务描述

冲突须在实现前提出，禁止自行选一种解释落地。

## 团队工程手册

详见 [project-management/README.md](project-management/README.md)。
