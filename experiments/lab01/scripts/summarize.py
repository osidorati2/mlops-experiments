#!/usr/bin/env python3
"""Сводка по каталогу results/<timestamp>: по каждому запуску и среднее ± stdev по конфигурации.

    python3 scripts/summarize.py results/20261025-200000

Границы метрик:
  idle      — memory.current после готовности, до прогрева;
  main max  — максимум memory.current по сэмплам основного замера (без прогрева);
  peak      — memory.peak за всё время жизни контейнера (старт, загрузка модели, прогрев, замер);
  cpu, thr  — разность cpu.stat до/после основного замера;
  oom main  — прирост memory.events oom_kill за основной замер;
  oom total — oom_kill за всё время жизни контейнера (+ флаг Docker OOMKilled);
  restarts  — сколько раз workers загружали модель сверх N (перезапуски после гибели).
OOM засчитывается по любому доступному источнику: oom_kill из cg-after.txt,
events.oom_kill из idle.txt/after.txt, флаг Docker OOMKilled.
Запуск без обязательных метрик помечается INCOMPLETE и считается неуспешным.
Код завершения 1, если хоть один запуск провалил тест, неполон или зафиксирован OOM.
"""

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

MIB = 1024 * 1024


def mib_field(path: Path, key: str):
    if not path.exists():
        return None
    m = re.search(rf"^{re.escape(key)}\s*:\s*([\d.]+) MiB", path.read_text(), re.M)
    return float(m.group(1)) if m else None


def samples_max(path: Path):
    if not path.exists():
        return None
    vals = [int(p[1]) for p in (l.split() for l in path.read_text().splitlines())
            if len(p) == 2 and p[1].isdigit()]
    return max(vals) / MIB if vals else None


def counters(path: Path):
    """Файл вида "cpu.stat.usage_usec 123" -> dict."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            out[parts[0]] = int(parts[1])
    return out


def oom_from_measure(path: Path):
    """events.oom_kill из вывода measure_memory.sh (резервный источник)."""
    if not path.exists():
        return None
    m = re.search(r"^events\.oom_kill\s+(\d+)", path.read_text(), re.M)
    return int(m.group(1)) if m else None


REQUIRED_COUNTERS = ("cpu.stat.usage_usec", "cpu.stat.nr_periods", "memory.events.oom_kill")


def delta(before, after, key):
    if key in before and key in after:
        return after[key] - before[key]
    return None


def fmt(xs, nd=1):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "NA"
    if len(xs) == 1:
        return f"{xs[0]:.{nd}f}"
    return f"{statistics.mean(xs):.{nd}f} ± {statistics.stdev(xs):.{nd}f}"


def num(x, width, nd=1):
    return f"{'NA':>{width}}" if x is None else f"{x:>{width}.{nd}f}"


def status(x):
    flags = [f for f, bad in (("FAIL", not x["passed"]), ("OOM", x["oom"]),
                              ("INCOMPLETE", bool(x["missing"]))) if bad]
    return "+".join(flags) or "ok"


def main():
    out = Path(sys.argv[1])
    rows = defaultdict(list)
    for load in sorted(out.glob("w*-r*-load.json")):
        n, r = map(int, re.match(r"w(\d+)-r(\d+)", load.name).groups())
        p = f"{load.parent}/w{n}-r{r}"
        d = json.loads(load.read_text())
        before, after = counters(Path(f"{p}-cg-before.txt")), counters(Path(f"{p}-cg-after.txt"))
        after_txt = Path(f"{p}-after.txt").read_text() if Path(f"{p}-after.txt").exists() else ""
        logs = Path(f"{p}-logs.txt").read_text() if Path(f"{p}-logs.txt").exists() else ""

        elapsed = d.get("elapsed_s") or 0
        usage = delta(before, after, "cpu.stat.usage_usec")
        periods = delta(before, after, "cpu.stat.nr_periods")
        throttled = delta(before, after, "cpu.stat.nr_throttled")
        thr_usec = delta(before, after, "cpu.stat.throttled_usec")
        oom_main = delta(before, after, "memory.events.oom_kill")
        oom_sources = [after.get("memory.events.oom_kill"),
                       oom_from_measure(Path(f"{p}-after.txt")),
                       oom_from_measure(Path(f"{p}-idle.txt"))]
        known = [x for x in oom_sources if x is not None]
        oom_total = max(known) if known else None
        docker_oom = "OOMKilled=true" in after_txt
        loads = len(re.findall(r"model loaded:", logs))

        idle = mib_field(Path(f"{p}-idle.txt"), "memory.current")
        main_max = samples_max(Path(f"{p}-samples.txt"))
        peak = mib_field(Path(f"{p}-after.txt"), "memory.peak")
        missing = [f"cg-before:{k}" for k in REQUIRED_COUNTERS if k not in before]
        missing += [f"cg-after:{k}" for k in REQUIRED_COUNTERS if k not in after]
        missing += [name for name, v in (("idle.memory.current", idle), ("samples", main_max),
                                         ("after.memory.peak", peak), ("logs", logs or None),
                                         ("after.OOMKilled", "OOMKilled=" in after_txt or None)) if v is None]

        rows[n].append({
            "run": r,
            "idle": idle,
            "main_max": main_max,
            "peak": peak,
            "rps": d.get("rps"),
            "p50": d["latency_ms"]["p50"],
            "p95": d["latency_ms"]["p95"],
            "p99": d["latency_ms"]["p99"],
            "ok": d["ok"],
            "err": sum(d["errors"].values()),
            "pids": len(d["requests_per_pid"]),
            "cpu": usage / 1e6 / elapsed if usage is not None and elapsed else None,
            "thr": 100 * throttled / periods if periods else (0.0 if periods == 0 else None),
            "thr_s": thr_usec / 1e6 if thr_usec is not None else None,
            "oom_main": oom_main,
            "oom_total": oom_total,
            "oom": docker_oom or bool(oom_total) or bool(oom_main),
            "restarts": max(0, loads - n),
            "passed": d.get("passed", False),
            "missing": missing,
        })

    print("Per run (memory: MiB; main max = max over main interval only; peak = container lifetime;")
    print("         cpu = cores used, thr = % CPU periods throttled, thr s = throttled time — all over main interval)")
    print(f"{'w':>2} {'run':>3} {'idle':>7} {'main max':>8} {'peak':>7} {'rps':>7} {'p50 ms':>7} {'p95 ms':>7} "
          f"{'p99 ms':>7} {'ok':>6} {'err':>4} {'pids':>4} {'cpu':>5} {'thr %':>6} {'thr s':>6} "
          f"{'oom main':>8} {'oom tot':>7} {'restart':>7} status")
    for n in sorted(rows):
        for x in rows[n]:
            print(f"{n:>2} {x['run']:>3} {num(x['idle'], 7)} {num(x['main_max'], 8)} {num(x['peak'], 7)} "
                  f"{num(x['rps'], 7)} {num(x['p50'], 7)} {num(x['p95'], 7)} {num(x['p99'], 7)} "
                  f"{x['ok']:>6} {x['err']:>4} {x['pids']:>4} {num(x['cpu'], 5, 2)} {num(x['thr'], 6)} "
                  f"{num(x['thr_s'], 6)} {str(x['oom_main'] if x['oom_main'] is not None else 'NA'):>8} "
                  f"{str(x['oom_total'] if x['oom_total'] is not None else 'NA'):>7} {x['restarts']:>7} {status(x)}")

    print("\nPer config: mean ± stdev")
    print(f"{'w':>2} {'runs':>4} {'idle MiB':>13} {'main max MiB':>13} {'peak MiB':>13} {'rps':>13} "
          f"{'p50 ms':>11} {'p95 ms':>11} {'p99 ms':>11} {'cpu cores':>11} {'thr %':>11}")
    for n in sorted(rows):
        xs = rows[n]
        col = lambda k: [x[k] for x in xs]
        print(f"{n:>2} {len(xs):>4} {fmt(col('idle')):>13} {fmt(col('main_max')):>13} {fmt(col('peak')):>13} "
              f"{fmt(col('rps')):>13} {fmt(col('p50')):>11} {fmt(col('p95')):>11} {fmt(col('p99')):>11} "
              f"{fmt(col('cpu'), 2):>11} {fmt(col('thr')):>11}")

    bad = [(f"w{n}-r{x['run']}", x) for n in sorted(rows) for x in rows[n] if status(x) != "ok"]
    if bad:
        print("\nWARNING: unsuccessful runs:")
        for name, x in bad:
            extra = f" (missing: {', '.join(x['missing'])})" if x["missing"] else ""
            print(f"  {name}: {status(x)}{extra}")
        sys.exit(1)


if __name__ == "__main__":
    main()
