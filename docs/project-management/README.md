# Mentora 团队工程手册

本目录用于把四人团队的职责分工转化为可执行的工程管理体系。
产品和技术架构仍以 `docs/architecture/` 为准，本目录负责定义人员职责、
交付顺序、协作方式和验收标准。

## 团队角色

| 角色 | 主要负责 | 支援方向 |
| --- | --- | --- |
| WH - 组长、后端与平台 | 总体架构、Django 领域服务、数据持久化、工作流、Electron Main/Preload、基础设施、阶段验收 | 项目协调、运维和性能诊断 |
| LBZ - 产品与前端 | React Renderer、用户流程、界面质量、前端测试 | Electron Renderer 集成和端到端测试 |
| LH - 资料与检索 | 资料接入、解析、证据、索引、检索评估 | AI 评测数据集 |
| LWJ - AI 学习与评测 | 模型网关、画像提取、计划生成、Tutor、题目验证 | 学习领域服务和测试数据 |

## 文档入口

- [团队章程](team-charter.md)：职责边界、RACI、接口所有权、评审规则、
  Definition of Ready 和 Definition of Done。
- [阶段交付路线图](delivery-roadmap.md)：六个研发阶段及其进入和退出标准。
- [第一阶段任务清单](stage-01-backlog.md)：第一个可执行的端到端阶段。
- [团队工程化执行计划](../superpowers/plans/2026-06-13-four-person-team-engineering.md)：
  启动团队协作机制和第一阶段的执行步骤。
- [任务模板](templates/task-template.md)：创建工程任务时必须填写的内容。
- [决策记录模板](templates/decision-record-template.md)：尚不需要完整 ADR 的轻量决策。

## 核心运行规则

每个阶段必须交付一条可以演示的端到端链路。阶段不按固定周数结束，
只有退出标准全部通过后才能进入下一阶段。只完成单独一层，
例如只有页面、只有接口或只有模型调用，不算完成交付。

```text
界面 -> API -> 持久化状态 -> 后台任务 -> 可观察结果 -> 自动化测试
```

## 文档优先级

文档出现冲突时，按以下顺序执行：

1. `docs/architecture/adr/` 下已接受的 ADR。
2. `docs/architecture/end-to-end-implementation-plan.md`。
3. `docs/architecture/module-boundaries.md`。
4. 本团队工程手册。
5. 当前阶段任务描述。

发现冲突时必须在实现前提出，不允许开发者自行选择一种解释后直接实现。
