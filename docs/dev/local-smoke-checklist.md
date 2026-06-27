# 本地启动与冒烟验证清单

本文档记录当前本地开发的基线流程，覆盖这次实际跑通的 API、Web、解析、刷题和环境变量边界。

## 启动基线

本地联调默认使用仓库根目录 `.env`。`apps/web/vite.config.ts` 从仓库根目录读取 `VITE_API_PROXY_TARGET`，因此 Web dev server 的 `/api/*` 请求应通过 Vite 代理转发到 Django API。

```powershell
copy .env.example .env
pnpm infra:up
pnpm api:migrate
pnpm api:seed
pnpm api:smoke:upload
pnpm dev:api
pnpm dev:web
```

关键环境变量：

- `POSTGRES_CONNECT_TIMEOUT=3`：数据库未启动时快速失败，避免 Django 启动检查长时间卡住。
- `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`：Vite `/api/*` 代理目标。
- `LLM_API_KEY`：本地未配置时，LLM 依赖接口应返回 503。

`.env` 是本地文件，不提交。

## HTTP 验证

```powershell
Invoke-RestMethod http://127.0.0.1:5173/api/health/
Invoke-RestMethod "http://127.0.0.1:5173/api/library/sources/?ownerId=dev-user"
curl.exe -F "file=@apps/api/tests/fixtures/normal.pdf" http://127.0.0.1:8000/api/parsing/preview
Invoke-RestMethod http://127.0.0.1:8000/api/parsing/benchmark
```

预期行为：

- `http://127.0.0.1:5173/api/health/` 返回 API 的 `{"status":"ok"}`，不是 Vite HTML。
- 资料列表能看到 `seed_dev` 创建的资料。
- 解析 preview 返回 bundle 和 `evidence_units`。
- DEBUG 环境下 parsing benchmark 可以使用本地 fixture；生产环境不得依赖这些 fixture。
- 未配置 `LLM_API_KEY` 时，课程规划、课程追问、刷题生成等 LLM 依赖接口返回 503，不返回 mock 结果，不返回假成功。

## 代码变更后的验证

涉及后端、前端代理、解析、刷题或环境变量的改动后，至少执行：

```powershell
uv run --isolated --no-project --with-editable apps/api --with pytest --with pytest-django --with django --with djangorestframework --with drf-spectacular --with psycopg[binary] --with pgvector --with pydantic --with PyMuPDF --with jieba --with boto3 --with botocore --with python-dotenv --with celery[redis] python -m pytest apps/api/tests/test_knowledge_library_api.py apps/api/tests/test_assessment_api.py apps/api/tests/test_parsing_api.py -q
uv run --isolated --no-project --with-editable apps/api --with django --with djangorestframework --with drf-spectacular --with psycopg[binary] --with pgvector --with pydantic --with PyMuPDF --with jieba --with boto3 --with botocore --with python-dotenv --with celery[redis] python apps/api/manage.py check
corepack pnpm typecheck:web
corepack pnpm --dir apps/web build
corepack pnpm --dir apps/desktop typecheck
git diff --check
```

## 与 mock / fixture 的边界

- 本地 `seed_dev`、测试 fixture、DEBUG-only benchmark 可以存在，但必须是显式开发入口。
- 产品运行路径不展示 mockQuiz、假解析结果、假任务变更或 API 失败后的成功 UI。
- 测试应显式传入 `course_session_id`、`source_version_ids` 等请求字段，不依赖开发兜底。

项目级 agent 工作流见 `docs/agents/README.md`。
