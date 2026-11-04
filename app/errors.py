"""Доменные ошибки: HTTP-слой переводит их в коды ответа."""


class InvalidImageError(Exception):
    """Файл пустой или не читается как изображение → 400."""


class PredictionError(Exception):
    """Предсказатель упал → 500/503."""


class StorageError(Exception):
    """Не удалось сохранить результат в БД → 500."""
