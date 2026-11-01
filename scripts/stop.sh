#!/usr/bin/env bash
# Остановить контейнеры эксперимента: ./scripts/stop.sh [1 2 4]
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh
for N in "${@:-1 2 4}"; do
  for n in $N; do docker rm -f "$(container_name "$n")" >/dev/null 2>&1 && echo "removed $(container_name "$n")" || true; done
done
