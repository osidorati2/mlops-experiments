"""Сценарий «классифицировать изображение»: проверка → предсказание → сохранение."""
from dataclasses import dataclass

from app.errors import PredictionError
from app.image_validation import load_image
from app.predictor import Predictor
from app.repository import HistoryItem, PredictionRepository


@dataclass(frozen=True)
class ClassificationResult:
    image_id: int
    prediction_id: int
    label: str
    model_version: str


class ClassificationService:
    def __init__(self, predictor: Predictor, repo: PredictionRepository) -> None:
        self._predictor = predictor
        self._repo = repo

    def classify(self, filename: str, data: bytes) -> ClassificationResult:
        """load_image → predictor.predict → repo.save; ошибки пробрасывает доменными исключениями."""
        image = load_image(data)  # InvalidImageError: до предсказателя и БД не доходим
        try:
            prediction = self._predictor.predict(image)
        except Exception as e:
            raise PredictionError("Predictor failed") from e
        saved = self._repo.save(filename, prediction)  # StorageError: успеха не будет
        return ClassificationResult(
            image_id=saved.image_id,
            prediction_id=saved.prediction_id,
            label=prediction.label,
            model_version=prediction.model_version,
        )

    def history(self) -> list[HistoryItem]:
        return self._repo.history()
