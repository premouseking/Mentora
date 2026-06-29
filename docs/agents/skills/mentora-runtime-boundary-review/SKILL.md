---
name: mentora-runtime-boundary-review
description: 审查 Mentora 中不安全的 mock 数据、硬编码运行时默认值、假 fallback 分支，以及开发环境和生产环境边界不清的问题。适用于移除 mock、增加环境变量、修改 API fallback、准备生产安全行为后的代码审查。
---

# Mentora 运行时边界审查

## 审查目标

重点审查运行时行为，不把 UI 文案、CSS 数值、测试 fixture、文档示例这类静态内容误判为生产风险。只要它们不参与生产控制流，就不需要为了“去硬编码”而机械替换。

优先处理这些风险：

- 生产构建或真实 API 页面仍能访问 mock 数据。
- API 失败后，前端或后端用假结果伪装成功。
- 凭证、host、owner、course ID、模型名、存储 key、功能行为没有通过配置管理。
- 本地开发默认值没有通过 `settings.DEBUG`、显式环境变量、测试配置或 fixture 路径隔离。
- 测试靠隐藏的开发 fallback 通过，而不是显式传入真实请求所需字段。

## 搜索

修改前先做聚焦搜索：

```powershell
rg -n "mock|fixture|fallback|hardcoded|TODO|DEV_|DEBUG|LLM_API_KEY|VITE_|ownerId|course_session_id|00000000|localhost|127\.0\.0\.1" apps docs .env.example
rg -n "mock|fixture|fallback|hardcoded" apps/web/src apps/api/mentora
rg -n "LLM_API_KEY|POSTGRES_|REDIS_URL|OBJECT_STORAGE_|VITE_API_PROXY_TARGET|MENTORA_" .env.example apps
```

按上下文解释搜索结果：

- 生产代码应该调用真实 API，并在依赖不可用时显式失败。
- 本地 fixture 应只存在于测试、管理命令、开发态 benchmark 接口或文档中。
- 后端返回错误时，前端不应合成成功的业务结果。
- 后端可以通过 `seed_dev` 这类显式命令提供本地样例数据，不应在普通请求里隐式兜底。

## 修复模式

1. 只有跨环境会变化的运行时值才替换为配置。
2. 不要替换所有静态字符串；UI 文案、枚举值、测试名、schema 字段名不是运行时配置。
3. LLM/provider 未配置时，API 返回显式 503，不返回假成功。
4. 本地专用行为必须有明确开发态开关，例如 DEBUG，并写入文档。
5. 测试要显式传入必要 ID 和请求字段，不依赖开发兜底。
6. 移除 fallback 后，必须跑本地 smoke，证明本地开发没有被破坏。

## 验证

任何边界调整后，都使用本地开发冒烟验证：

- library、assessment、parsing 的后端 targeted tests。
- `manage.py check`.
- Web typecheck 和 production build。
- 通过 Vite 代理做 HTTP smoke。
- 未配置 `LLM_API_KEY` 的 LLM 依赖接口应返回 503。

任何有意保留的本地 fixture，都要写入 `docs/dev/local-infrastructure.md` 或相关 API README。
