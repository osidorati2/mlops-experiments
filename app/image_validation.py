"""Проверка, что байты — читаемое изображение; ничего не знает про HTTP и БД."""
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import InvalidImageError


def load_image(data: bytes) -> Image.Image:
    """Декодирует байты в изображение, иначе бросает InvalidImageError."""
    if not data:
        raise InvalidImageError("Empty file")
    try:
        image = Image.open(BytesIO(data))
        image.load()  # open() читает только заголовок; load() декодирует пиксели целиком
    except UnidentifiedImageError:
        raise InvalidImageError("File is not a recognized image") from None
    except (OSError, SyntaxError, ValueError):
        raise InvalidImageError("Image is corrupted or truncated") from None
    return image
