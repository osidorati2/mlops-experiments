"""Подключение к SQLite и создание схемы (images, predictions)."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id      INTEGER NOT NULL REFERENCES images(id),
    class         TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    """Открывает соединение с включёнными foreign keys."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI выполняет sync-эндпоинты в пуле потоков, поэтому разрешаем доступ из разных потоков.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # в SQLite по умолчанию выключено
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Создаёт таблицы, если их ещё нет."""
    with conn:
        conn.executescript(SCHEMA)
