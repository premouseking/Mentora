import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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
