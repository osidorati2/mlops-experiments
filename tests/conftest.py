"""Общие фикстуры: SQLite в памяти, тестовые PNG-байты, фейковые предсказатели."""
import pytest
from PIL import Image


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (8, 8), "white")
