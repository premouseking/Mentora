"""
模型调用网关：统一路由、Provider 适配、结构化输出校验与调用审计。

约定：
- 领域模块不直接调用 Provider SDK，统一通过 ModelGateway.chat() / chat_stream()
- task_type 用于路由和审计，不影响请求内容
- 每次实际网络调用创建 ModelAttempt 审计记录

约束：
- Provider 替换不影响网关接口签名
- 结构化输出校验在 Provider 返回后立即执行
- 模块不依赖 agent_runtime 或任何领域模块

@see docs/architecture/agent-runtime-design.md §9
@module mentora/model_gateway
"""
