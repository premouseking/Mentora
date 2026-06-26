import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass

# ── 加载 .env（stdlib 手动解析，无 python-dotenv 依赖）──

def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_dotenv()

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

# ── Embedding Provider ────────────────────────────────────

# 当前使用：doubao（豆包 Embedding，火山引擎）
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "doubao")
EMBEDDING_DOUBAO_API_KEY = os.getenv("VOLCANO_ENGINE_API_KEY", "")
EMBEDDING_DOUBAO_MODEL = os.getenv("EMBEDDING_DOUBAO_MODEL", "doubao-embedding")
# MRL 降维：2048 → 1024，平衡性能与存储
EMBEDDING_DOUBAO_DIMENSIONS = int(os.getenv("EMBEDDING_DOUBAO_DIMENSIONS", "1024"))
EMBEDDING_DOUBAO_BASE_URL = os.getenv(
    "EMBEDDING_DOUBAO_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3",
)

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
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", os.getenv("LLM_TIMEOUT_S", "60")))
LLM_STREAM_TIMEOUT = int(os.getenv("LLM_STREAM_TIMEOUT", "120"))

MODEL_GATEWAY = {
    "max_retries_per_attempt": LLM_MAX_RETRIES,
    "timeout_s": float(LLM_REQUEST_TIMEOUT),
}
