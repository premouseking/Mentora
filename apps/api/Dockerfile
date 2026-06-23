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

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
