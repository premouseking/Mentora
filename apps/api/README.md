# Mentora API

## 前置条件

- Python **3.11+**
- 仓库根目录已复制 `.env.example` → `.env`，并已执行 `pnpm infra:up`（PostgreSQL / Redis / MinIO）

完整本地基础设施说明见 [docs/dev/local-infrastructure.md](../../docs/dev/local-infrastructure.md)。

## 环境准备

在 `apps/api` 目录下执行。**必须在当前目录安装**，不要在仓库根目录对 `apps/api` 做相对路径 editable install。

### 方式 A：venv（推荐）

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
python manage.py migrate
python manage.py seed_dev
```

### 方式 B：Conda（可选）

```powershell
cd apps\api
conda create -n mentora-api python=3.11 -y
conda activate mentora-api
python -m pip install -U pip
python -m pip install -e ".[dev]"
python manage.py migrate
python manage.py seed_dev
```

## 运行

```powershell
python manage.py runserver 127.0.0.1:8000
```

根目录也可使用 `pnpm dev:api`。

在独立终端中启动 worker（异步解析验证时）：

```powershell
celery -A config worker -Q heavy -n heavy@%h --loglevel=info
```

## 开发命令

| 命令 | 说明 |
| --- | --- |
| `python manage.py seed_dev` | 填充最小闭环样例（fixture PDF + 解析证据） |
| `python manage.py smoke_upload_resource` | 资源库上传 smoke |
| `python manage.py smoke_upload_resource --via-http` | 通过 HTTP API 跑上传链路 |
| `python manage.py validate_retrieval` | 检查 pgvector 扩展与检索表 |

根目录等价脚本：`pnpm api:seed`、`pnpm api:smoke:upload`。

## API 端点（当前）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health/` | 健康检查 |
| POST | `/api/uploads/` | 创建上传会话，返回预签名 URL |
| POST | `/api/uploads/complete/` | 完成上传，创建 SourceVersion 并解析 |
| GET | `/api/library/sources/` | 列出资源库资料 |
| POST | `/api/parsing/preview` | PDF 解析预览（不入库） |
| GET | `/api/parsing/benchmark` | 解析基准测试 |

## 测试

CI / 无 MinIO 时使用 filesystem 对象存储后端：

```powershell
$env:OBJECT_STORAGE_BACKEND="filesystem"
pytest
```

## 云端迁移

对象存储与数据库设计见 [docs/dev/cloud-migration.md](../../docs/dev/cloud-migration.md)。

## 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `No module named 'django'` | 未激活 venv | 激活 `.venv` 后 `pip install -e ".[dev]"` |
| 连接 PostgreSQL 失败 | infra 未启动或端口冲突 | `pnpm infra:up`，检查 `POSTGRES_PORT` |
| MinIO 连接失败 | MinIO 未启动 | `pnpm infra:up`；或测试时设 `OBJECT_STORAGE_BACKEND=filesystem` |
| `Multiple top-level packages discovered` | 旧版 pyproject | 确认 `[tool.setuptools.packages.find]` 已存在 |

验证安装：

```powershell
python -c "import django; print(django.get_version())"
python manage.py check
python manage.py smoke_upload_resource --fixture normal.pdf
```
