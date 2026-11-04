#!/usr/bin/env python3
"""Ограниченный нагрузочный тест (только stdlib).

Нагрузка всегда конечна: фиксированная конкурентность и либо фиксированное
число запросов, либо фиксированная длительность; всё ограничено потолками.

Тест считается успешным, если есть хотя бы один успешный ответ и доля ошибок
не превышает --max-error-rate (по умолчанию 0). Иначе код завершения 1;
сводка (с ошибками) печатается и сохраняется в любом случае.

Примеры:
    python3 scripts/load_test.py --url http://127.0.0.1:8002 --requests 1000 --concurrency 8
    python3 scripts/load_test.py --url http://127.0.0.1:8002 --duration 60 --concurrency 8
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

MAX_REQUESTS = 5000
MAX_CONCURRENCY = 32
MAX_WARMUP_SECONDS = 30
MAX_DURATION_SECONDS = 120


def one_request(url: str, timeout: float):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = json.loads(r.read())
        return time.perf_counter() - t0, body.get("pid"), body.get("work_ms"), None
    except Exception as e:  # noqa: BLE001 — считаем любую ошибку
        return time.perf_counter() - t0, None, None, type(e).__name__


def run_for(url: str, seconds: float, concurrency: int, timeout: float):
    """`concurrency` потоков шлют запросы подряд в течение `seconds` секунд.

    Новые запросы после дедлайна не начинаются; уже отправленные дожидаются ответа.
    """
    deadline = time.perf_counter() + seconds

    def loop():
        out = []
        while time.perf_counter() < deadline:
            out.append(one_request(url, timeout))
        return out

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        return [r for chunk in ex.map(lambda _: loop(), range(concurrency)) for r in chunk]


def percentile(data, q):
    if not data:
        return None
    data = sorted(data)
    k = min(len(data) - 1, max(0, round(q / 100 * (len(data) - 1))))
    return data[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8001")
    ap.add_argument("--path", default="/work")
    ap.add_argument("--requests", type=int, default=1000)
    ap.add_argument("--duration", type=float, default=0,
                    help="длительность основного замера в секундах; если > 0, --requests игнорируется")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--warmup-seconds", type=float, default=7.0,
                    help="длительность прогрева (0 — без прогрева)")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-error-rate", type=float, default=0.0,
                    help="допустимая доля ошибок основного замера (0..1)")
    ap.add_argument("--warmup-only", action="store_true",
                    help="только прогрев, без основного замера (для run_experiment.sh)")
    ap.add_argument("--json-out", help="сохранить сводку в JSON-файл")
    a = ap.parse_args()

    if not (1 <= a.requests <= MAX_REQUESTS):
        sys.exit(f"--requests must be in [1, {MAX_REQUESTS}]")
    if not (1 <= a.concurrency <= MAX_CONCURRENCY):
        sys.exit(f"--concurrency must be in [1, {MAX_CONCURRENCY}]")
    if not (0 <= a.warmup_seconds <= MAX_WARMUP_SECONDS):
        sys.exit(f"--warmup-seconds must be in [0, {MAX_WARMUP_SECONDS}]")
    if not (0 <= a.duration <= MAX_DURATION_SECONDS):
        sys.exit(f"--duration must be in [0, {MAX_DURATION_SECONDS}]")
    if not (0 <= a.max_error_rate <= 1):
        sys.exit("--max-error-rate must be in [0, 1]")
    if a.warmup_only and a.warmup_seconds <= 0:
        sys.exit("--warmup-only requires --warmup-seconds > 0")

    url = a.url.rstrip("/") + a.path
    if a.warmup_seconds > 0:
        # Результаты прогрева отбрасываются; в stderr — только сводка,
        # чтобы stdout оставался чистым JSON основного замера.
        w = run_for(url, a.warmup_seconds, a.concurrency, a.timeout)
        wpids = Counter(r[1] for r in w if r[3] is None)
        print(f"warmup: {a.warmup_seconds:g}s concurrency={a.concurrency} "
              f"requests={len(w)} errors={sum(r[3] is not None for r in w)} "
              f"pids={dict(sorted(wpids.items()))}", file=sys.stderr)
        if a.warmup_only:
            sys.exit(0 if wpids else 1)

    # Основной замер начинается с чистой статистики.
    t0 = time.perf_counter()
    if a.duration > 0:
        results = run_for(url, a.duration, a.concurrency, a.timeout)
    else:
        with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
            results = list(ex.map(lambda _: one_request(url, a.timeout), range(a.requests)))
    elapsed = time.perf_counter() - t0

    lat_ms = [r[0] * 1000 for r in results if r[3] is None]
    work_ms = [r[2] for r in results if r[2] is not None]
    errors = Counter(r[3] for r in results if r[3] is not None)
    pids = Counter(r[1] for r in results if r[1] is not None)

    n_err = sum(errors.values())
    error_rate = n_err / len(results) if results else 1.0
    if not lat_ms:
        fail_reason = "no successful responses"
    elif error_rate > a.max_error_rate:
        fail_reason = f"error rate {error_rate:.4f} > {a.max_error_rate}"
    else:
        fail_reason = None

    def r1(x):
        return None if x is None else round(x, 1)

    summary = {
        "passed": fail_reason is None,
        "fail_reason": fail_reason,
        "url": url,
        "requests": len(results),
        "duration_s": a.duration or None,
        "concurrency": a.concurrency,
        "warmup_seconds": a.warmup_seconds,
        "ok": len(lat_ms),
        "errors": dict(errors),
        "error_rate": round(error_rate, 4),
        "elapsed_s": round(elapsed, 2),
        "rps": round(len(lat_ms) / elapsed, 1) if elapsed > 0 else None,
        "latency_ms": {
            "p50": r1(percentile(lat_ms, 50)),
            "p95": r1(percentile(lat_ms, 95)),
            "p99": r1(percentile(lat_ms, 99)),
            "max": r1(max(lat_ms)) if lat_ms else None,
        },
        "server_work_ms_mean": round(statistics.mean(work_ms), 2) if work_ms else None,
        "requests_per_pid": dict(sorted(pids.items())),
    }
    # allow_nan=False — гарантия стандартного JSON (никаких NaN/Infinity).
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))
    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump(summary, f, indent=2, allow_nan=False)
    if fail_reason:
        print(f"FAILED: {fail_reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
