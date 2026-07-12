FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY manage.py ./
COPY config ./config
COPY mentora ./mentora

# 构建时写入源码哈希，供启动前镜像校验
ARG MENTORA_API_SOURCE_HASH=""
RUN if [ -n "$MENTORA_API_SOURCE_HASH" ]; then echo "$MENTORA_API_SOURCE_HASH" > /app/.source-hash; fi
LABEL mentora.api.source_hash=${MENTORA_API_SOURCE_HASH}

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
