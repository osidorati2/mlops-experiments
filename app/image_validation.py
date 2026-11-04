"""Проверка, что байты — читаемое изображение; ничего не знает про HTTP и БД."""
from PIL import Image


def load_image(data: bytes) -> Image.Image:
    """Декодирует байты в изображение, иначе бросает InvalidImageError."""
    ...
