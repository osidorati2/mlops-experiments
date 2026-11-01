#!/usr/bin/env bash
# Запуск контейнера с N workers: ./scripts/run.sh 1|2|4
#   READY_TIMEOUT=90  — сколько секунд ждать готовности всех workers
#   MODEL_SIZE_MIB=128 — размер «модели» на worker (для опытов с OOM)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

N="${1:?usage: $0 <workers: 1|2|4>}"
NAME="$(container_name "$N")"
PORT="$(host_port "$N")"
READY_TIMEOUT="${READY_TIMEOUT:-90}"

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  "${LIMITS[@]}" \
  -e WORKERS="$N" \
  -e MODEL_SIZE_MIB="${MODEL_SIZE_MIB:-128}" \
  -p "127.0.0.1:${PORT}:8000" \
  "$IMAGE" >/dev/null

echo "started $NAME (workers=$N) on http://127.0.0.1:${PORT}"

# PID живых worker-процессов внутри контейнера. При N=1 uvicorn работает
# в одном процессе (PID 1), при N>1 workers — дети PID 1 через multiprocessing.spawn.
alive_workers() {
  docker exec "$NAME" sh -c '
    if [ "$1" -eq 1 ]; then echo 1; exit; fi
    for d in /proc/[0-9]*; do
      [ "$(awk "/^PPid:/{print \$2}" $d/status 2>/dev/null)" = 1 ] || continue
      tr "\0" " " < $d/cmdline 2>/dev/null | grep -q spawn_main && echo "${d#/proc/}"
    done' sh "$N" 2>/dev/null | sort -n
}

# Готов = ровно N живых workers, и каждый из них (по своему PID) написал
# "model loaded". Строки уже умерших процессов не засчитываются.
# /health с таймаутом подтверждает, что порт принимает запросы.
deadline=$((SECONDS + READY_TIMEOUT))
while [ "$SECONDS" -lt "$deadline" ]; do
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]; then
    echo "container exited; OOMKilled=$(docker inspect -f '{{.State.OOMKilled}}' "$NAME")" >&2
    docker logs "$NAME" >&2
    exit 1
  fi
  pids="$(alive_workers || true)"
  loaded_pids="$(docker logs "$NAME" 2>&1 | sed -n 's/.*model loaded:.* pid=\([0-9]*\)$/\1/p' | sort -un)"
  alive=$(printf '%s\n' $pids | grep -c . || true)
  # comm требует лексикографической сортировки: оба списка сортируются
  # одинаково в локали C (численная сортировка ломает пересечение: 8 10 vs 8 9 10).
  ready=$(comm -12 <(printf '%s\n' $pids | LC_ALL=C sort -u) \
                   <(printf '%s\n' $loaded_pids | LC_ALL=C sort -u) | grep -c . || true)
  if [ "$alive" -eq "$N" ] && [ "$ready" -eq "$N" ] &&
     curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "ready: $ready/$N live workers loaded model (pids: $(echo $pids))"
    exit 0
  fi
  sleep 1
done
echo "timeout after ${READY_TIMEOUT}s waiting for $NAME: alive=${alive:-0}/$N ready=${ready:-0}/$N" >&2
docker exec "$NAME" grep -E '^oom_kill ' /sys/fs/cgroup/memory.events >&2 2>/dev/null || true
docker logs --tail 20 "$NAME" >&2
exit 1
