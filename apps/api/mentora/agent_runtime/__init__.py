"""
Agent 运行时框架：多 Agent 调度、工具调用、提示词管理和上下文预算控制。

约定：
- Agent 不拥有领域事实，只通过 Tool 调用领域服务
- 所有 Agent 运行通过审计模型持久化
- 模型调用统一经过 model_gateway 路由

@see docs/architecture/agent-runtime-design.md
@module mentora/agent_runtime
"""
