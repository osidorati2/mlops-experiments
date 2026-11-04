"""Весь SQL сервиса: атомарная запись изображения+предсказания и чтение истории."""
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.errors import StorageError
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
        # Соединение общее для всех потоков: без блокировки транзакции разных запросов перемешаются.
        self._lock = threading.Lock()

    def save(self, filename: str, prediction: Prediction) -> SavedPrediction:
        """Вставляет images и predictions в одной транзакции; при ошибке — откат и StorageError."""
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self._conn:  # `with conn` делает commit или rollback
                image_id = self._conn.execute(
                    "INSERT INTO images (filename) VALUES (?)", (filename,)
                ).lastrowid
                prediction_id = self._conn.execute(
                    "INSERT INTO predictions (image_id, class, model_version, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (image_id, prediction.label, prediction.model_version, created_at),
                ).lastrowid
        except sqlite3.Error as e:
            raise StorageError("Failed to save prediction") from e
        return SavedPrediction(image_id=image_id, prediction_id=prediction_id)

    def history(self) -> list[HistoryItem]:
        """Предсказания с именами изображений (JOIN images), новые сверху."""
        try:
            with self._lock:  # только чтение: транзакция не нужна, но соединение общее
                rows = self._conn.execute(
                    "SELECT predictions.id AS prediction_id, predictions.image_id, images.filename, "
                    "predictions.class, predictions.model_version, predictions.created_at "
                    "FROM predictions "
                    "JOIN images ON predictions.image_id = images.id "
                    "ORDER BY predictions.created_at DESC, predictions.id DESC"
                ).fetchall()
        except sqlite3.Error as e:
            raise StorageError("Failed to load history") from e
        return [
            HistoryItem(
                prediction_id=row["prediction_id"],
                image_id=row["image_id"],
                filename=row["filename"],
                label=row["class"],  # в Python `class` — зарезервированное слово
                model_version=row["model_version"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
