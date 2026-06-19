import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# 仓库根：apps/api -> apps -> smartStudy。.env 与 .env.example 均位于此处。
REPO_ROOT = BASE_DIR.parent.parent

# 启动时加载 .env，使本地开发无需手动注入环境变量。
# 约束：不覆盖已存在的进程环境变量（CI / 容器注入优先），缺少 .env 时静默跳过。
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "pgvector.django",
    "mentora.courses",
    "mentora.knowledge",
    "mentora.learning",
    "mentora.assessment",
    "mentora.agent_runtime",
    "mentora.parsing",
    "mentora.retrieval",
    "mentora.model_gateway",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "mentora"),
        "USER": os.getenv("POSTGRES_USER", "mentora"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "mentora"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "55432"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
CELERY_TASK_ROUTES = {
    "mentora.knowledge.tasks.*": {"queue": "heavy"},
    "mentora.knowledge.tasks.run_processing": {"queue": "heavy"},
    "mentora.parsing.tasks.*": {"queue": "heavy"},
    "mentora.agent_runtime.tasks.*": {"queue": "agent"},
    "mentora.learning.tasks.*": {"queue": "learning"},
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── 对象存储（MinIO / S3 / COS 同构）────────────────────

OBJECT_STORAGE_BACKEND = os.getenv("OBJECT_STORAGE_BACKEND", "s3")
OBJECT_STORAGE_ENDPOINT = os.getenv("OBJECT_STORAGE_ENDPOINT", "http://127.0.0.1:9000")
OBJECT_STORAGE_BUCKET = os.getenv("OBJECT_STORAGE_BUCKET", "mentora")
OBJECT_STORAGE_ACCESS_KEY = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "mentora")
OBJECT_STORAGE_SECRET_KEY = os.getenv("OBJECT_STORAGE_SECRET_KEY", "mentora-secret")
OBJECT_STORAGE_REGION = os.getenv("OBJECT_STORAGE_REGION", "us-east-1")
OBJECT_STORAGE_FS_ROOT = os.getenv("OBJECT_STORAGE_FS_ROOT", "/tmp/mentora/storage")

# ── 开发种子数据 ─────────────────────────────────────────

DEV_OWNER_ID = os.getenv("DEV_OWNER_ID", "dev-user")

# ── pgvector ─────────────────────────────────────────────

# pgvector 是 PostgreSQL 扩展，Django 引擎仍使用默认 PostgreSQL 后端。
# 首次部署时须在 PostgreSQL 中执行：
#   CREATE EXTENSION IF NOT EXISTS vector;
#   CREATE EXTENSION IF NOT EXISTS pg_trgm;
# 参考: infra/docker/init/01-extensions.sql

# IVFFlat 索引的 lists 参数（约等于 sqrt(行数)）
PGVECTOR_IVFFLAT_LISTS = 100
# 向量搜索的探测数（查询时使用，越大召回越准但越慢）
PGVECTOR_PROBES = 10

# ── 模型网关 ─────────────────────────────────────────────
#
# 领域服务通过 mentora.model_gateway 调用大模型，不直接接触下方配置。
# 默认 provider 为 OpenAI 兼容端点：DeepSeek / 通义千问 / Moonshot / 智谱 等
# 均可通过 LLM_BASE_URL + 模型名接入，无需新增适配器。
# 新增厂商或质量档只需扩展 providers / routing，无需改动网关与领域代码。

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_ORGANIZATION = os.getenv("LLM_ORGANIZATION", "") or None

# 各质量档对应的模型名，可按所选厂商覆盖。
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", "gpt-4o-mini")
LLM_MODEL_BALANCED = os.getenv("LLM_MODEL_BALANCED", "gpt-4o-mini")
LLM_MODEL_PREMIUM = os.getenv("LLM_MODEL_PREMIUM", "gpt-4o")

MODEL_GATEWAY = {
    "providers": {
        "openai_compatible": {
            "class": "mentora.model_gateway.providers.openai_compatible.OpenAICompatibleProvider",
            "options": {
                "api_key": LLM_API_KEY,
                "base_url": LLM_BASE_URL,
                "organization": LLM_ORGANIZATION,
            },
        },
    },
    # 每个质量档给出「主选 + Fallback」候选序列，网关按序尝试。
    "routing": {
        "fast": [{"provider": "openai_compatible", "model": LLM_MODEL_FAST}],
        "balanced": [
            {"provider": "openai_compatible", "model": LLM_MODEL_BALANCED},
            {"provider": "openai_compatible", "model": LLM_MODEL_FAST},
        ],
        "premium": [
            {"provider": "openai_compatible", "model": LLM_MODEL_PREMIUM},
            {"provider": "openai_compatible", "model": LLM_MODEL_BALANCED},
        ],
    },
    # 单候选内瞬时错误的额外重试次数（总尝试 = 1 + 该值）。
    "max_retries_per_attempt": int(os.getenv("LLM_MAX_RETRIES", "1")),
    "timeout_s": float(os.getenv("LLM_TIMEOUT_S", "60")),
}
