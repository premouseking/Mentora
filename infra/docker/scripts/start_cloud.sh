#!/usr/bin/env bash
# 云端一键启动：基础设施 + API + Web + Worker，供 systemd 或手动调用。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/.env" -f "$ROOT/infra/docker/docker-compose.dev.yml" --profile app)

echo "==> 启动 Mentora 基础设施"
docker compose --env-file "$ROOT/.env" -f "$ROOT/infra/docker/docker-compose.dev.yml" up -d postgres redis minio

echo "==> 构建/启动 API（必要时重建镜像）"
bash "$ROOT/infra/docker/scripts/start_api.sh"

echo "==> 启动 Web 与 Worker"
"${COMPOSE[@]}" up -d web worker

echo "==> 等待 Web 就绪"
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:5173/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -sf "http://127.0.0.1:5173/" >/dev/null; then
  echo "Web 启动超时，最近日志：" >&2
  docker logs mentora-web-1 --tail 30 >&2 || docker logs mentora-web --tail 30 >&2 || true
  exit 1
fi

if ! curl -sf "http://127.0.0.1/api/health/" >/dev/null; then
  echo "Nginx/API 代理检查失败，请确认 nginx 已 reload" >&2
  exit 1
fi

echo "==> Mentora 云端栈已就绪"
echo "    前端: http://127.0.0.1/ (nginx) 或 :5173"
echo "    API:  http://127.0.0.1/api/health/"
