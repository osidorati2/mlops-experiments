# Общие параметры эксперимента. Подключается через `source`.
IMAGE="${IMAGE:-worker-mem-exp:latest}"
# Одинаковые ограничения для всех запусков:
#   2 CPU, 1 GiB RAM, swap отключён (memory-swap == memory),
#   чтобы при нехватке памяти процесс убивался OOM-killer'ом, а не уходил в swap.
LIMITS=(--cpus=2 --memory=1g --memory-swap=1g --pids-limit=256)

container_name() { echo "mem-w$1"; }
host_port() { echo "$((8000 + $1))"; }   # 1 -> 8001, 2 -> 8002, 4 -> 8004
