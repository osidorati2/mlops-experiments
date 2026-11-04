#!/usr/bin/env bash
# Снимок памяти всего контейнера и его процессов: ./scripts/measure_memory.sh mem-w2
set -euo pipefail
C="${1:?usage: $0 <container-name>}"

echo "=== docker stats ($C) ==="
# Docker вычитает из usage неактивный page cache, поэтому цифра может быть
# немного меньше memory.current.
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}\t{{.PIDs}}' "$C"

echo
echo "=== cgroup (весь контейнер) ==="
docker exec "$C" sh -c '
mib() { awk -v b="$1" "BEGIN{printf \"%.1f MiB\", b/1048576}"; }
if [ -f /sys/fs/cgroup/memory.current ]; then          # cgroup v2
  echo "memory.current : $(mib $(cat /sys/fs/cgroup/memory.current))"
  [ -f /sys/fs/cgroup/memory.peak ] && echo "memory.peak    : $(mib $(cat /sys/fs/cgroup/memory.peak))"
  echo "memory.max     : $(cat /sys/fs/cgroup/memory.max)"
  for k in anon file kernel shmem; do
    v=$(awk -v k=$k "\$1==k{print \$2}" /sys/fs/cgroup/memory.stat)
    [ -n "$v" ] && printf "%-15s: %s\n" "stat.$k" "$(mib $v)"
  done
  grep -E "^oom_kill " /sys/fs/cgroup/memory.events | sed "s/^/events./"
else                                                     # cgroup v1
  echo "usage   : $(mib $(cat /sys/fs/cgroup/memory/memory.usage_in_bytes))"
  echo "max     : $(mib $(cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes))"
  grep -E "^(total_rss|total_cache) " /sys/fs/cgroup/memory/memory.stat
fi
'

echo
echo "=== процессы (RSS / PSS) ==="
# PSS делит общие страницы между процессами, поэтому сумма PSS ~ реальная
# занятость, а сумма RSS может быть завышена из-за общих библиотек.
docker exec "$C" sh -c '
printf "%-6s %-6s %10s %10s %10s  %s\n" PID PPID RSS_MiB PSS_MiB ANON_MiB CMD
tr=0; tp=0
for d in /proc/[0-9]*; do
  p=${d#/proc/}
  [ "$p" = "$$" ] && continue   # не считать сам этот shell
  [ -r $d/smaps_rollup ] || continue
  rss=$(awk "/^VmRSS:/{print \$2}" $d/status); [ -n "$rss" ] || continue
  ppid=$(awk "/^PPid:/{print \$2}" $d/status)
  pss=$(awk "/^Pss:/{print \$2}" $d/smaps_rollup)
  anon=$(awk "/^RssAnon:/{print \$2}" $d/status)
  cmd=$(tr "\0" " " < $d/cmdline | cut -c1-70)
  case "$cmd" in *python*|*uvicorn*) ;; *) continue;; esac
  printf "%-6s %-6s %10.1f %10.1f %10.1f  %s\n" $p $ppid $(awk "BEGIN{print $rss/1024}") $(awk "BEGIN{print $pss/1024}") $(awk "BEGIN{print $anon/1024}") "$cmd"
  tr=$((tr+rss)); tp=$((tp+pss))
done
awk -v r=$tr -v p=$tp "BEGIN{printf \"total: RSS=%.1f MiB  PSS=%.1f MiB\n\", r/1024, p/1024}"
'
