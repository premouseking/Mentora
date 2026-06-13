# Mentora API

## 前置条件

- Python **3.11+**
- 仓库根目录已复制 `.env.example` → `.env`，并已执行 `pnpm infra:up`（PostgreSQL / Redis / MinIO）

## 环境准备

在 `apps/api` 目录下执行。**必须在当前目录安装**，不要在仓库根目录对 `apps/api` 做相对路径 editable install。

### 方式 A：venv（推荐，与文档默认一致）

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
python manage.py migrate
```

激活后提示符应显示 `(.venv)`；`python -c "import django"` 不应报错。

### 方式 B：Conda（可选）

```powershell
cd apps\api
conda create -n mentora-api python=3.11 -y
conda activate mentora-api
python -m pip install -U pip
python -m pip install -e ".[dev]"
python manage.py migrate
```

## 运行

```powershell
python manage.py runserver 127.0.0.1:8000
```

在独立终端中启动 worker（需已激活同一 Python 环境）：

```powershell
celery -A config worker -Q heavy -n heavy@%h --loglevel=info
celery -A config worker -Q agent -n agent@%h --loglevel=info
celery -A config worker -Q learning -n learning@%h --loglevel=info
```

## 测试

```powershell
pytest
```

## 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `No module named 'django'` | 未激活 venv/conda，或仍在 `(base)` 等未安装依赖的环境 | 激活 `.venv` 或 `mentora-api` 后重装：`pip install -e ".[dev]"` |
| `Multiple top-level packages discovered` | 旧版 `pyproject.toml` 未声明包发现 | 拉取最新代码；确认 `[tool.setuptools.packages.find]` 已存在 |
| `pip install -e` 在仓库根目录失败 | editable 路径与 `manage.py` 工作目录不一致 | 进入 `apps/api` 再执行安装命令 |

验证安装是否成功：

```powershell
python -c "import django; print(django.get_version())"
python manage.py check
```
