"""Общие фикстуры: SQLite в памяти, тестовые PNG-байты, фейковые предсказатели."""
import os
import sqlite3
from io import BytesIO

import pytest
from PIL import Image

# До импорта app.*: app.main создаёт приложение при импорте, и оно не должно трогать data/app.db.
os.environ["DB_PATH"] = ":memory:"

from app import db  # noqa: E402


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (8, 8), "white")


@pytest.fixture
def png_bytes(image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def conn() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    yield conn
    conn.close()
