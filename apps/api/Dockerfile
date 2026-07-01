FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY manage.py ./
COPY config ./config
COPY mentora ./mentora
COPY tests/fixtures ./tests/fixtures

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
