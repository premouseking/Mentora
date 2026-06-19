"""
模型网关：领域服务声明任务需求，网关负责选型、调用、Fallback 与输出校验。

约定：
- 领域服务只构造 ModelRequest（声明 task_type / quality_tier / 结构化 schema 等），
  绝不直接 import 任何模型厂商 SDK。
- 网关返回 ModelResponse（候选结果），业务校验与字段授权由领域服务执行。

@see docs/architecture/end-to-end-implementation-plan.md §8.2
@see docs/architecture/module-boundaries.md
@module mentora/model_gateway
"""
