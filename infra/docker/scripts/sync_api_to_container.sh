#!/usr/bin/env bash
# 开发热补丁：将工作区 apps/api 同步到运行中的 API 容器（不重建镜像）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CONTAINER="${MENTORA_API_CONTAINER:-mentora-api-1}"

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "容器 $CONTAINER 不存在" >&2
  exit 1
fi

echo "==> 同步 apps/api → $CONTAINER:/app"
tar -C "$ROOT/apps/api" -cf - config mentora manage.py | docker exec -i "$CONTAINER" tar xf - -C /app

echo "==> 重启 API"
docker restart "$CONTAINER" >/dev/null
sleep 12

echo "==> 校验容器路由与模块（镜像哈希过期时仅告警，不阻断热同步）"
python3 "$ROOT/infra/docker/scripts/check_api_image.py" --require-container --allow-stale-image
