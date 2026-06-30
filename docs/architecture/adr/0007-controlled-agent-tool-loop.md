# ADR-0007：学习 Agent 采用受控多轮 Tool-Loop 内核

- 状态：Accepted
- 日期：2026-06-16
- 关联设计：`docs/architecture/technical-solution.md` §2、`docs/architecture/module-boundaries.md`

## 背景

Mentora 需要支持开放推理场景（如 Tutor 带引用问答、资料探索），要求模型能按需调用
检索等工具，并在多轮对话中维持上下文。参考 Codex 的 `run_turn` 循环 的
`runTurn`，核心机制是：**模型调用 → 解析 tool_calls → 执行工具 → 结果回填 history →
再调模型**，直到模型不再请求工具或达到迭代上限。

现有文档（`module-boundaries.md` §6、`end-to-end-implementation-plan.md` §20/§21）
主张业务流程用显式持久状态机、有限次 `model_gateway` 调用，不上长 tool-loop。本 ADR
记录偏离该主张的决策边界：开放推理走受控 tool-loop，结构化业务流程仍走状态机。

## 决策

1. 在 `mentora.agent_runtime` 落地通用 Agent 内核：`ToolRegistry` + 有上限的多轮
   tool-loop + `ContextManager` + 提示词拼接。
2. 工具调用走模型原生 function-calling，由 `model_gateway` 透传 `tools` / `tool_calls`，
   不靠提示词手写 JSON 协议。
3. 工具实现**只能调用领域服务**（如 `retrieval.search`），禁止直接写领域表。
4. 每轮 turn 设硬上限（默认 12 轮），超限终止并返回错误，防止无限循环。
5. Agent checkpoint / 内存 history **不是**学生状态或课程状态的唯一来源；领域事实仍
   由 courses / learning 等领域服务持久化。
6. 首版先做同步 loop（`gateway.complete`），流式 token / SSE / DB checkpoint 作为后续
   阶段，通过 `AgentEvent` 回调预留接缝。
7. 提示词采用 Codex 式分离：base instructions（模板文件）与对话 history 分开组装；
   动态上下文（资料范围、证据快照 ID）作为 message 注入 history，不由前端拼接。

## 约束

| 层 | 做什么 | 不做什么 |
| --- | --- | --- |
| `agent_runtime` | 推进 tool-loop、组装 ContextView、调度工具 | 不拥有课程/学习事实；不 import 厂商 SDK |
| 领域服务 | 提供只读/受控写能力供工具调用 | 不拼 provider 逻辑 |
| `model_gateway` | 路由/重试/Fallback/结构化校验/tool_calls 透传 | 不做业务字段授权 |

## 后果

- 正面：开放推理场景可复用统一 Agent 内核；与 Codex/Lightest 心智模型一致；工具可
  渐进扩展。
- 负面：与部分早期文档表述不一致；需后续补 `workflow_runtime` 编排层与持久 checkpoint。
- 缓解：结构化业务流程（澄清、计划、出题）仍走状态机 + Schema 校验，不强制走 tool-loop。

## 参考

- Codex `codex-rs/core/src/session/turn.rs` — turn 级模型↔工具循环
- Lightest `packages/agent-core/src/runTurn.ts` — 有上限的 tool-loop 状态机
