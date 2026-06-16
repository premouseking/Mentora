# 本地开发基础设施

每位开发者运行**独立**的 PostgreSQL、Redis、MinIO，不共用某人的本机数据库。

## 前置条件

- Docker Desktop（或兼容的 Docker Compose）
- Python 3.11+（API）
- Node.js + pnpm（Web/Desktop）

## 快速启动

```powershell
# 1. 复制环境变量（仓库根目录）
copy .env.example .env

# 2. 启动基础设施
pnpm infra:up

# 3. API 环境（在 apps/api 目录）
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
python manage.py migrate
python manage.py seed_dev
python manage.py smoke_upload_resource --fixture normal.pdf
python manage.py runserver 127.0.0.1:8000
```

或使用根目录脚本：

```powershell
pnpm infra:up
pnpm api:migrate
pnpm api:seed
pnpm api:smoke:upload
pnpm dev:api
```

Compose 项目名固定为 `mentora`，本地容器/网络/卷名称会使用 `mentora-*` 或 `mentora_*` 前缀。

可选：如果希望 API 也运行在 Docker 中：

```powershell
pnpm api:docker:build
pnpm api:docker:up
curl http://127.0.0.1:8000/api/health/
```

## 服务端口

| 服务 | 默认端口 | 环境变量 |
| --- | --- | --- |
| PostgreSQL | 55432 | `POSTGRES_PORT` |
| Redis | 6379 | `REDIS_URL` |
| MinIO API | 9000 | `OBJECT_STORAGE_ENDPOINT` |
| MinIO Console | 9001 | — |
| Django API | 8000 | — |
| Vite Web | 5173 | — |

## Docker 化边界

| 组件 | 建议 | 原因 |
| --- | --- | --- |
| PostgreSQL / Redis / MinIO | 已放入默认 compose | 本地基础设施应可一键重建 |
| Django API | 可选 `app` profile | 依赖边界清楚，适合验证云端同构运行 |
| Celery Worker | 下一步可加入 `app` profile | 需要异步解析压测或后台队列时再启用 |
| Web renderer | 暂不放入本地默认 compose | Vite 本机开发反馈更快；生产可另做静态镜像 |
| Electron Desktop | 不放入 Docker | Electron 是本机桌面打包目标，需要系统窗口/签名/安装器环境 |

## 端口冲突

本地 Docker PostgreSQL 默认映射到 `55432`，避免和常见的本机 PostgreSQL `5432` 冲突。若 `55432` 也被占用，修改 `.env` 中的 `POSTGRES_PORT`，`docker-compose.dev.yml` 会同步使用该端口。

## 重建本地数据库

开发数据可丢弃时：

```powershell
pnpm infra:down
docker volume rm mentora_postgres_data mentora_redis_data mentora_minio_data
pnpm infra:up
pnpm api:migrate
pnpm api:seed
```

注意：`docker volume rm` 会删除本地开发数据，执行前确认无需要保留的内容。

## 对象存储

- 本地：MinIO（S3 兼容），bucket 默认 `mentora`
- 测试/CI：设置 `OBJECT_STORAGE_BACKEND=filesystem`，无需 MinIO
- 云端：COS/S3，仅改环境变量与 endpoint，不改业务表

`seed_dev` 与 `smoke_upload_resource` 会在首次运行时自动创建 bucket（s3 后端）。

## Celery Worker（可选）

解析任务默认可同步执行（`complete` 与 smoke 命令）。异步验证时：

```powershell
celery -A config worker -Q heavy -n heavy@%h --loglevel=info
```

## 验证清单

```powershell
python manage.py check
python manage.py validate_retrieval
curl http://127.0.0.1:8000/api/health/
curl http://127.0.0.1:8000/api/library/sources/
```

## 相关文档

- [云端迁移边界](cloud-migration.md)
- [共享 dev/staging 环境](shared-dev-environment.md)
- [最小业务闭环](minimal-loop.md)
- [API README](../../apps/api/README.md)
