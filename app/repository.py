"""Весь SQL сервиса: атомарная запись изображения+предсказания и чтение истории."""
import sqlite3
from dataclasses import dataclass

from app.predictor import Prediction


@dataclass(frozen=True)
class SavedPrediction:
    image_id: int
    prediction_id: int


@dataclass(frozen=True)
class HistoryItem:
    prediction_id: int
    image_id: int
    filename: str
    label: str
    model_version: str
    created_at: str


class PredictionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, filename: str, prediction: Prediction) -> SavedPrediction:
        """Вставляет images и predictions в одной транзакции; при ошибке — откат и StorageError."""
        ...

    def history(self) -> list[HistoryItem]:
        """Предсказания с именами изображений (JOIN images)."""
        ...
