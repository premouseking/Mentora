#!/usr/bin/env bash
# 启动 API 容器：先校验/重建镜像，再 up，最后做健康与路由抽检。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/.env" -f "$ROOT/infra/docker/docker-compose.dev.yml" --profile app)
SCRIPTS="$ROOT/infra/docker/scripts"

echo "==> 计算工作区 API 源码哈希"
WORKSPACE_HASH="$("$SCRIPTS/compute_api_source_hash.py")"
echo "    $WORKSPACE_HASH"

IMAGE_HASH=""
if docker image inspect mentora-api >/dev/null 2>&1; then
  IMAGE_HASH="$(docker image inspect mentora-api --format '{{ index .Config.Labels "mentora.api.source_hash" }}')"
fi

if [[ -z "$IMAGE_HASH" || "$IMAGE_HASH" != "$WORKSPACE_HASH" ]]; then
  echo "==> 镜像过期或不存在，重新构建 mentora-api"
  export MENTORA_API_SOURCE_HASH="$WORKSPACE_HASH"
  bash "$SCRIPTS/build_api_image.sh"
else
  echo "==> 镜像源码哈希一致，跳过构建"
fi

echo "==> 启动 API 容器"
"${COMPOSE[@]}" up -d api

echo "==> 等待健康检查"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${API_PORT:-8000}/api/health/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sf "http://127.0.0.1:${API_PORT:-8000}/api/health/" >/dev/null; then
  echo "API 健康检查失败" >&2
  docker logs mentora-api-1 --tail 40 >&2 || true
  exit 1
fi

echo "==> 校验镜像与路由"
python3 "$SCRIPTS/check_api_image.py" --require-container

echo "==> API 已就绪: http://127.0.0.1:${API_PORT:-8000}/api/health/"
