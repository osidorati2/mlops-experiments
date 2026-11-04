"""Учебный сервис для эксперимента с памятью worker-процессов.

Каждый worker при старте (lifespan) отдельно выделяет и заполняет буфер,
имитирующий веса модели. Буфер не разделяется между процессами.
"""

import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

MIB = 1024 * 1024
MODEL_SIZE_MIB = int(os.getenv("MODEL_SIZE_MIB", "128"))
# Фиксированный объём CPU-работы на запрос; одинаков для всех запусков.
WORK_ROUNDS = int(os.getenv("WORK_ROUNDS", "2000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s pid=%(process)d %(message)s",
)
log = logging.getLogger("mem-experiment")

model: bytearray | None = None


def load_model(size_mib: int) -> bytearray:
    """Выделяет буфер и записывает в него ненулевые данные.

    Простой bytearray(size) может получить «ленивые» нулевые страницы, которые
    не попадают в RSS до первой записи. Умножение bytearray заполняет каждый
    байт значением 0xA5, поэтому все страницы реально становятся резидентными.
    """
    buf = bytearray(b"\xa5") * (size_mib * MIB)
    # Пишем по байту в каждую страницу ещё раз — явная гарантия, что всё «тронуто».
    page = 4096
    buf[::page] = b"\x5a" * len(range(0, len(buf), page))
    return buf


@asynccontextmanager
async def lifespan(_: FastAPI):
    global model
    pid = os.getpid()
    log.info("model loading started: size=%d MiB ppid=%d", MODEL_SIZE_MIB, os.getppid())
    t0 = time.perf_counter()
    model = load_model(MODEL_SIZE_MIB)
    log.info(
        "model loaded: size=%d MiB bytes=%d took=%.2fs pid=%d",
        MODEL_SIZE_MIB, len(model), time.perf_counter() - t0, pid,
    )
    yield
    log.info("worker shutting down, releasing model")
    model = None


app = FastAPI(title="worker-memory-experiment", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok" if model is not None else "loading",
        "pid": os.getpid(),
        "model_loaded": model is not None,
        "model_size_mib": MODEL_SIZE_MIB,
    }


@app.get("/work")
def work():
    """Одинаковая детерминированная CPU-нагрузка без sleep.

    Обычная (sync) функция: FastAPI выполнит её в threadpool и не заблокирует
    event loop, поэтому /health остаётся отзывчивым. Данные читаются из
    «модели», но объём работы не зависит от числа workers.
    """
    assert model is not None
    t0 = time.perf_counter()
    digest = model[:64]
    for _ in range(WORK_ROUNDS):
        digest = hashlib.sha256(digest).digest()
    acc = 0
    for i in range(0, 20_000):
        acc = (acc * 31 + model[(i * 4099) % len(model)]) & 0xFFFFFFFF
    return {
        "pid": os.getpid(),
        "result": digest.hex()[:16],
        "acc": acc,
        "work_ms": round((time.perf_counter() - t0) * 1000, 2),
    }
