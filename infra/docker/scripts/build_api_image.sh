#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export MENTORA_API_SOURCE_HASH="$("$ROOT/infra/docker/scripts/compute_api_source_hash.py")"

echo "构建 mentora-api（源码哈希 ${MENTORA_API_SOURCE_HASH:0:12}…）"
docker compose --env-file "$ROOT/.env" \
  -f "$ROOT/infra/docker/docker-compose.dev.yml" \
  --profile app \
  build api
