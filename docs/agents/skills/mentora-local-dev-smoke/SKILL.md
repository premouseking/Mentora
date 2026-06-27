---
name: mentora-local-dev-smoke
description: 在 D:\AllCode\smartStudy 启动并验证 Mentora 本地开发栈。适用于用户要求本地跑起来、代码修改后验证 API/Web/Desktop、排查本地基础设施启动问题，或确认真实 API 路径在没有 mock fallback 的情况下可用。
---

# Mentora 本地开发冒烟验证

## 工作流程

在仓库根目录使用本 skill，默认环境是 Windows/PowerShell。除非用户要求停止服务，否则验证结束后保持本地服务运行。

1. 修改前先检查工作区。
   - 运行 `git status --short`。
   - 不要暂存或删除 `.vscode/`、`.env`、无关未跟踪文件。

2. 准备本地环境变量。
   - 确认仓库根目录存在 `.env`。如果没有，从 `.env.example` 复制，并填写本地开发值。
   - `.env` 必须保持未提交。
   - 默认使用 PostgreSQL `55432`、Redis `56379`、MinIO `9000/9001`。
   - 确认存在 `POSTGRES_CONNECT_TIMEOUT`，这样数据库没启动时能快速失败。

3. 启动基础设施。
   - 如果 Docker 没有运行，先启动 Docker Desktop，并等待 `docker info` 成功。
   - 运行 `corepack pnpm infra:up`。
   - 确认 `mentora-postgres-1`、`mentora-redis-1`、`mentora-minio-1` healthy 或处于监听状态。

4. 初始化 API 数据。
   - seed 或 smoke 之前先跑迁移：
     `uv run --isolated --no-project --with-editable apps/api --with django --with djangorestframework --with drf-spectacular --with psycopg[binary] --with pgvector --with pydantic --with PyMuPDF --with jieba --with boto3 --with botocore --with python-dotenv --with celery[redis] python apps/api/manage.py migrate --noinput`
   - 运行 `seed_dev`。
   - 运行 `smoke_upload_resource --fixture normal.pdf`。

5. 启动开发服务。
   - API：Django 监听 `127.0.0.1:8000`。
   - Web：运行 `corepack pnpm --dir apps/web dev --host 127.0.0.1`。
   - 如果用后台进程启动，把日志重定向到仓库外，例如 `$env:TEMP`，避免留下 `.codex-*.log`。

6. 验证真实 HTTP 行为。
   - `http://127.0.0.1:5173/api/health/` 必须通过 Vite 代理打到 API，并返回 `status=ok`。
   - `GET /api/library/sources/?ownerId=dev-user` 应返回 seed 后的资料。
   - 用 `apps/api/tests/fixtures/normal.pdf` 调 `POST /api/parsing/preview`，应返回 `evidence_units`。
   - `GET /api/parsing/benchmark` 应返回 fixture 结果；DEBUG 下可以使用本地 benchmark fixture。
   - 未配置 `LLM_API_KEY` 时，`POST /api/assessment/sessions/generate/` 应返回 503，不应返回 mock 题目，也不应 500。

7. 代码变更后运行验证命令。
   - 后端：
     `uv run --isolated --no-project --with-editable apps/api --with pytest --with pytest-django --with django --with djangorestframework --with drf-spectacular --with psycopg[binary] --with pgvector --with pydantic --with PyMuPDF --with jieba --with boto3 --with botocore --with python-dotenv --with celery[redis] python -m pytest apps/api/tests/test_knowledge_library_api.py apps/api/tests/test_assessment_api.py apps/api/tests/test_parsing_api.py -q`
   - Django check：
     `uv run --isolated --no-project --with-editable apps/api --with django --with djangorestframework --with drf-spectacular --with psycopg[binary] --with pgvector --with pydantic --with PyMuPDF --with jieba --with boto3 --with botocore --with python-dotenv --with celery[redis] python apps/api/manage.py check`
   - Web：`corepack pnpm typecheck:web` 和 `corepack pnpm --dir apps/web build`。
   - Desktop：`corepack pnpm --dir apps/desktop typecheck`。
   - Git 空白检查：`git diff --check`。

## 失败处理

- 如果 `/api/health/` 返回 Vite `index.html`，检查 `apps/web/vite.config.ts` 是否从仓库根目录读取 env，并确认 `VITE_API_PROXY_TARGET` 指向 `http://127.0.0.1:8000`。
- 如果 pytest 报 `gin_trgm_ops` 或 `vector`，检查 retrieval migration 是否为测试库创建 `pg_trgm` 和 `vector` 扩展。
- 如果 LLM 相关接口因为缺少凭证失败，除非用户提供真实本地 key，否则应保持显式 503。
- 如果命令在仓库里生成临时日志，只清理自己生成的日志，不要碰用户文件。
