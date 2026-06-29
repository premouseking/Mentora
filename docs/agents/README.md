# 项目级 Agent Skill

本目录沉淀 Mentora 仓库内可复用的 agent 工作流。它们不是运行时业务代码，也不是用户侧产品文档；用途是让后续 agent 在处理本仓库任务时，先读取稳定流程，再执行具体操作。

## 当前 skill

| Skill | 适用场景 |
| --- | --- |
| `mentora-local-dev-smoke` | 本地启动 API/Web/Desktop、跑 migrate/seed/smoke、验证真实 API 和 Vite 代理。 |
| `mentora-runtime-boundary-review` | 审查 mock、硬编码运行时值、开发/生产边界和假 fallback。 |

## 使用约定

- 涉及本地启动、联调、冒烟验证时，先读 `docs/agents/skills/mentora-local-dev-smoke/SKILL.md`。
- 涉及 mock、fixture、硬编码、环境变量、生产安全边界时，先读 `docs/agents/skills/mentora-runtime-boundary-review/SKILL.md`。
- skill 中记录的是仓库操作流程；如果流程变化，更新 skill 和 `docs/dev/` 文档，避免只留在聊天记录里。
