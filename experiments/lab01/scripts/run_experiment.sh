#!/usr/bin/env bash
# Полный прогон: для каждого числа workers и каждого повтора по очереди
#   свежий контейнер -> замер в простое -> прогрев -> [снимок cgroup ->
#   основной замер с сэмплированием памяти -> снимок cgroup] -> замер после
#   нагрузки -> логи -> остановка.
# Контейнеры запускаются строго по одному, чтобы не конкурировать за CPU/RAM хоста.
#
#   ./scripts/run_experiment.sh                          # workers 1 2 4, 1 повтор, 1000 запросов
#   RUNS=3 DURATION=60 ./scripts/run_experiment.sh       # 3 повтора по 60 с на конфигурацию
#   REQUESTS=500 CONCURRENCY=8 WARMUP_S=10 ./scripts/run_experiment.sh 2
#
# Код завершения: 0 — все запуски прошли; код первого упавшего нагрузочного
# теста — если какой-то тест провалился (остальные запуски всё равно выполняются);
# исходный код ошибки — если упал сам скрипт (запуск контейнера, измерение).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

REQUESTS="${REQUESTS:-1000}"
DURATION="${DURATION:-0}"          # > 0 — основной замер по времени, REQUESTS игнорируется
CONCURRENCY="${CONCURRENCY:-8}"
WARMUP_S="${WARMUP_S:-7}"
SETTLE_S="${SETTLE_S:-5}"
RUNS="${RUNS:-1}"
OUT="results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
LIST=("$@"); [ ${#LIST[@]} -gt 0 ] || LIST=(1 2 4)

# Состояние текущего запуска — для очистки при любом выходе.
CUR_NAME=""; CUR_P=""; SAMPLER=""; FLAG=""; LOAD_PID=""

stop_sampler() {
  [ -n "$FLAG" ] && rm -f "$FLAG"
  if [ -n "$SAMPLER" ]; then
    kill "$SAMPLER" 2>/dev/null || true
    wait "$SAMPLER" 2>/dev/null || true
  fi
  SAMPLER=""; FLAG=""
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [ -n "$LOAD_PID" ]; then
    kill "$LOAD_PID" 2>/dev/null || true
    wait "$LOAD_PID" 2>/dev/null || true
  fi
  stop_sampler
  if [ -n "$CUR_NAME" ]; then
    echo "cleanup (exit code $rc): saving diagnostics and removing $CUR_NAME" >&2
    if docker inspect "$CUR_NAME" >/dev/null 2>&1; then
      docker logs "$CUR_NAME" > "$CUR_P-logs.txt" 2>&1 || true
      docker inspect -f 'OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}} Running={{.State.Running}}' \
        "$CUR_NAME" > "$CUR_P-state.txt" 2>&1 || true
      docker rm -f "$CUR_NAME" >/dev/null 2>&1 || true
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Нагрузочный тест в фоне + wait: bash выполняет trap только между командами,
# а `wait` прерывается сигналом сразу — иначе SIGTERM ждал бы конца 60-секундного замера.
run_load() {
  python3 scripts/load_test.py "$@" &
  LOAD_PID=$!
  local rc=0
  wait "$LOAD_PID" || rc=$?
  LOAD_PID=""
  return "$rc"
}

# Счётчики cgroup v2 в формате "<файл>.<ключ> <значение>".
cg_snapshot() {
  docker exec "$1" sh -c '
    for f in cpu.stat memory.events; do
      sed "s/^/$f./" /sys/fs/cgroup/$f
    done
    echo "memory.current $(cat /sys/fs/cgroup/memory.current)"'
}

echo "workers=${LIST[*]} runs=$RUNS concurrency=$CONCURRENCY warmup=${WARMUP_S}s duration=${DURATION}s requests=$REQUESTS" | tee "$OUT/params.txt"
docker build -q -t "$IMAGE" . >/dev/null

FIRST_FAIL=0
FAILED_RUNS=()

for N in "${LIST[@]}"; do
  for R in $(seq 1 "$RUNS"); do
    NAME="$(container_name "$N")"; PORT="$(host_port "$N")"; P="$OUT/w$N-r$R"
    CUR_NAME="$NAME"; CUR_P="$P"
    URL="http://127.0.0.1:$PORT"
    echo "########## workers=$N run=$R/$RUNS ##########"
    ./scripts/run.sh "$N"
    sleep "$SETTLE_S"

    ./scripts/measure_memory.sh "$NAME" > "$P-idle.txt"
    grep -E '^memory.current' "$P-idle.txt"

    # Прогрев — отдельным вызовом, чтобы граница основного замера была точной.
    if [ "$WARMUP_S" != "0" ]; then
      run_load --url "$URL" --concurrency "$CONCURRENCY" \
        --warmup-seconds "$WARMUP_S" --warmup-only
    fi

    # Основной интервал: снимок cgroup до и после, сэмплер памяти — только здесь.
    cg_snapshot "$NAME" > "$P-cg-before.txt"

    # Сэмплер memory.current раз в 0.5 с; останавливается сам, когда
    # пропадает файл-флаг, и не дольше 600 сэмплов (~5 мин).
    FLAG="$P.sampling"; touch "$FLAG"
    (
      for _ in $(seq 1 600); do
        [ -f "$FLAG" ] || break
        echo "$(date +%s) $(docker exec "$NAME" cat /sys/fs/cgroup/memory.current 2>/dev/null || echo NA)"
        sleep 0.5
      done
    ) > "$P-samples.txt" &
    SAMPLER=$!

    LT_RC=0
    run_load --url "$URL" \
      --requests "$REQUESTS" --duration "$DURATION" \
      --concurrency "$CONCURRENCY" --warmup-seconds 0 \
      --json-out "$P-load.json" > /dev/null || LT_RC=$?

    stop_sampler
    # Сбой снимка не прерывает сбор диагностики, но запуск не теряется молча:
    # summarize.py пометит его INCOMPLETE, и эксперимент завершится с кодом 1.
    cg_snapshot "$NAME" > "$P-cg-after.txt" ||
      echo "WARNING: cgroup snapshot after main interval failed (w$N-r$R)" >&2

    ./scripts/measure_memory.sh "$NAME" > "$P-after.txt" ||
      echo "WARNING: memory measurement after load failed (w$N-r$R)" >&2
    docker logs "$NAME" > "$P-logs.txt" 2>&1
    echo "OOMKilled=$(docker inspect -f '{{.State.OOMKilled}}' "$NAME")" >> "$P-after.txt"
    python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print('passed',d['passed'],'rps',d['rps'],'p50',d['latency_ms']['p50'],'p95',d['latency_ms']['p95'],'errors',d['errors'])" "$P-load.json" || true

    if [ "$LT_RC" -ne 0 ]; then
      echo "load test FAILED for workers=$N run=$R (exit $LT_RC)" >&2
      FAILED_RUNS+=("w$N-r$R")
      [ "$FIRST_FAIL" -ne 0 ] || FIRST_FAIL=$LT_RC
    fi

    ./scripts/stop.sh "$N"
    CUR_NAME=""; CUR_P=""
  done
done

echo
SUM_RC=0
python3 scripts/summarize.py "$OUT" | tee "$OUT/summary.txt" || SUM_RC=$?

if [ "$FIRST_FAIL" -ne 0 ]; then
  echo "failed runs: ${FAILED_RUNS[*]}" | tee -a "$OUT/summary.txt" >&2
  exit "$FIRST_FAIL"
fi
exit "$SUM_RC"   # 1, если сводка нашла OOM или неполный запуск при успешных тестах
