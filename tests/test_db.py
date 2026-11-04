"""Схема создаётся, повторный init безопасен, внешний ключ и NOT NULL работают."""
import sqlite3

import pytest

from app import db


def columns(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_tables_and_columns(conn):
    assert columns(conn, "images") == ["id", "filename"]
    assert columns(conn, "predictions") == ["id", "image_id", "class", "model_version", "created_at"]


def test_init_schema_is_idempotent_and_keeps_data(conn):
    conn.execute("INSERT INTO images (filename) VALUES ('cat.png')")
    conn.commit()

    db.init_schema(conn)

    assert conn.execute("SELECT count(*) FROM images").fetchone()[0] == 1


def test_foreign_key_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO predictions (image_id, class, model_version, created_at)"
            " VALUES (999, 'cat', 'stub-v1', '2026-01-01T00:00:00Z')"
        )


def test_not_null_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO images (filename) VALUES (NULL)")


def test_connect_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "app.db"

    db.init_schema(db.connect(str(path)))

    assert path.exists()
