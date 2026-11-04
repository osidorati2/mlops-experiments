"""Общие фикстуры: SQLite в памяти, тестовые PNG-байты, фейковые предсказатели."""
from io import BytesIO

import pytest
from PIL import Image


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (8, 8), "white")


@pytest.fixture
def png_bytes(image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
