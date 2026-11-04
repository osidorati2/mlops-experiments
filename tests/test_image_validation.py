"""Валидный PNG проходит; пустые байты и текст → InvalidImageError."""
import pytest

from app.errors import InvalidImageError
from app.image_validation import load_image


def test_valid_png(png_bytes):
    assert load_image(png_bytes).size == (8, 8)


@pytest.mark.parametrize("data", [b"", b"hello, i am not an image"])
def test_empty_or_text_rejected(data):
    with pytest.raises(InvalidImageError):
        load_image(data)


def test_truncated_png_rejected(png_bytes):
    with pytest.raises(InvalidImageError):
        load_image(png_bytes[: len(png_bytes) // 2])
