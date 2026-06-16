# 共享 dev / staging 环境

本地闭环稳定后，可提供**共享集成环境**用于联调与演示。该环境**不替代**每位开发者的本地数据库。

## 适用场景

- 前后端接口联调
- 产品演示
- PR 合并前冒烟
- 非后端成员连接统一 dev API

## 不适用场景

- 日常功能开发默认数据库（多人写入会导致数据污染、迁移状态不一致）
- 单元测试与 CI（应使用隔离库或 filesystem 后端）

## 推荐架构

```text
dev-api.mentora.example
  -> 托管 PostgreSQL（独立 dev 实例）
  -> 托管 Redis
  -> COS/S3 dev bucket
  -> Celery workers（heavy / agent / learning 队列）

staging-api.mentora.example
  -> 与 dev 隔离的 DB + bucket
  -> 用于发布前验收
```

## 数据策略

- `seed_dev` 仅用于本地；共享 dev 可用 `seed_demo`（后续）或手动 seed
- 禁止将生产 dump 导入 dev
- 定期重置 dev 数据库（例如每周），并文档化重置窗口

## 客户端连接

桌面/Web 通过环境变量指向共享 API：

```text
MENTORA_API_BASE_URL=https://dev-api.example.com/api
VITE_API_BASE_URL=https://dev-api.example.com/api
```

## 实施顺序

1. 本地 `migrate + seed_dev + smoke_upload_resource` 稳定
2. 部署 dev API + 托管依赖（同构配置）
3. 配置 CI 对 dev 环境跑 HTTP smoke（可选）
4. staging 与 dev 完全隔离 bucket 与数据库
