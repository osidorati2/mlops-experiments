"""Подключение к SQLite и создание схемы (images, predictions)."""
import sqlite3

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
    ...


def init_schema(conn: sqlite3.Connection) -> None:
    """Создаёт таблицы, если их ещё нет."""
    ...
