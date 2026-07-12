import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass


def _env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"{name} is required")


def _env_list(name: str) -> list[str]:
    return [item.strip() for item in _env(name).split(",") if item.strip()]


SECRET_KEY = _env("DJANGO_SECRET_KEY")
DEBUG = _env("DJANGO_DEBUG").lower() == "true"
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")
if "PYTEST_CURRENT_TEST" in os.environ and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

AUTH_USER_MODEL = "users.User"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "pgvector.django",
    "mentora.users",
    "mentora.courses",
    "mentora.knowledge",
    "mentora.learning",
    "mentora.assessment",
    "mentora.agent_runtime",
    "mentora.parsing",
    "mentora.retrieval",
    "mentora.topics",
    "mentora.model_gateway",
    "mentora.workflow_runtime",
    "drf_spectacular",
]

from datetime import timedelta

# 开发模式认证旁路仍注入真实 User，业务层始终只依赖 request.user。
MENTORA_DEV_AUTH_BYPASS = DEBUG and os.getenv("MENTORA_DEV_AUTH_BYPASS", "0") == "1"
DEV_USER_EMAIL = os.getenv("DEV_USER_EMAIL", "dev@mentora.local")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        ["config.authentication.DevelopmentUserAuthentication"] if MENTORA_DEV_AUTH_BYPASS else
        ["rest_framework_simplejwt.authentication.JWTAuthentication"]
    ),
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Mentora API",
    "DESCRIPTION": "Mentora 智能学习工作空间 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

MIDDLEWARE = [
    "config.cors.CorsMiddleware",
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
        "NAME": _env("POSTGRES_DB"),
        "USER": _env("POSTGRES_USER"),
        "PASSWORD": _env("POSTGRES_PASSWORD"),
        "HOST": _env("POSTGRES_HOST"),
        "PORT": _env("POSTGRES_PORT"),
        "OPTIONS": {"connect_timeout": int(_env("POSTGRES_CONNECT_TIMEOUT"))},
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

CELERY_BROKER_URL = _env("REDIS_URL")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _env("REDIS_URL"),
    },
}
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
CELERY_TASK_ROUTES = {
    "mentora.knowledge.tasks.*": {"queue": "heavy"},
    "mentora.knowledge.tasks.run_processing": {"queue": "heavy"},
    "mentora.parsing.tasks.*": {"queue": "heavy"},
    "mentora.retrieval.tasks.*": {"queue": "heavy"},
    "mentora.agent_runtime.tasks.*": {"queue": "agent"},
    "mentora.workflow_runtime.tasks.*": {"queue": "agent"},
    "mentora.learning.tasks.*": {"queue": "learning"},
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── 对象存储（MinIO / S3 / COS 同构）────────────────────

OBJECT_STORAGE_BACKEND = _env("OBJECT_STORAGE_BACKEND")
OBJECT_STORAGE_ENDPOINT = _env("OBJECT_STORAGE_ENDPOINT")
OBJECT_STORAGE_PUBLIC_ENDPOINT = os.getenv(
    "OBJECT_STORAGE_PUBLIC_ENDPOINT",
    OBJECT_STORAGE_ENDPOINT,
)
OBJECT_STORAGE_BUCKET = _env("OBJECT_STORAGE_BUCKET")
OBJECT_STORAGE_ACCESS_KEY = _env("OBJECT_STORAGE_ACCESS_KEY")
OBJECT_STORAGE_SECRET_KEY = _env("OBJECT_STORAGE_SECRET_KEY")
OBJECT_STORAGE_REGION = _env("OBJECT_STORAGE_REGION")
OBJECT_STORAGE_FS_ROOT = _env("OBJECT_STORAGE_FS_ROOT")

# ── 开发种子数据 ─────────────────────────────────────────

DEV_OWNER_ID = _env("DEV_OWNER_ID")
DEV_COURSE_SESSION_ID = os.getenv("DEV_COURSE_SESSION_ID")

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

# ── Embedding Provider ────────────────────────────────────

# 当前使用：doubao（豆包 Embedding，火山引擎）
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "doubao")
EMBEDDING_DOUBAO_API_KEY = os.getenv("VOLCANO_ENGINE_API_KEY", "")
EMBEDDING_DOUBAO_MODEL = os.getenv("EMBEDDING_DOUBAO_MODEL", "doubao-embedding")
EMBEDDING_DOUBAO_ENDPOINT_ID = os.getenv("EMBEDDING_DOUBAO_ENDPOINT_ID", "")
# MRL 降维：2048 → 1024，平衡性能与存储
EMBEDDING_DOUBAO_DIMENSIONS = int(os.getenv("EMBEDDING_DOUBAO_DIMENSIONS", "1024"))
EMBEDDING_DOUBAO_BASE_URL = os.getenv(
    "EMBEDDING_DOUBAO_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3",
)
EMBEDDING_DOUBAO_BATCH_SIZE = int(os.getenv("EMBEDDING_DOUBAO_BATCH_SIZE", "1"))  # 多模态 API 限单条

# ── 多模态 Provider ──────────────────────────────────────

# 豆包多模态：Vision 模型做图片描述，Embedding Vision 做图文联合向量
MULTIMODAL_API_KEY = os.getenv("MULTIMODAL_API_KEY", os.getenv("VOLCANO_ENGINE_API_KEY", ""))
MULTIMODAL_BASE_URL = os.getenv(
    "MULTIMODAL_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3",
)
MULTIMODAL_VISION_MODEL = os.getenv(
    "MULTIMODAL_VISION_MODEL", "doubao-1-5-vision-pro-32k"
)
MULTIMODAL_EMBED_MODEL = os.getenv(
    "MULTIMODAL_EMBED_MODEL", "doubao-embedding-vision-250615"
)

# ── Reranker ─────────────────────────────────────────────

# Qwen3-Reranker-4B via SiliconFlow
RERANKER_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B")

# ── LLM 配置（通过环境变量注入，参考 .env.example）─────

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1"),
)
LLM_API_BASE_URL = LLM_BASE_URL
LLM_ORGANIZATION = os.getenv("LLM_ORGANIZATION", "") or None

LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", os.getenv("LLM_MODEL", "gpt-4o-mini"))
LLM_MODEL_BALANCED = os.getenv("LLM_MODEL_BALANCED", LLM_MODEL_FAST)
LLM_MODEL_PREMIUM = os.getenv("LLM_MODEL_PREMIUM", LLM_MODEL_BALANCED)
LLM_MODEL = LLM_MODEL_BALANCED
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", os.getenv("LLM_TIMEOUT_S", "120")))
LLM_STREAM_TIMEOUT = int(os.getenv("LLM_STREAM_TIMEOUT", "120"))
LLM_STRUCTURED_TIMEOUT = int(os.getenv("LLM_STRUCTURED_TIMEOUT", "300"))

MODEL_GATEWAY = {
    "max_retries_per_attempt": LLM_MAX_RETRIES,
    "timeout_s": float(LLM_REQUEST_TIMEOUT),
}
