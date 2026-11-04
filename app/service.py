"""Сценарий «классифицировать изображение»: проверка → предсказание → сохранение."""
from app.predictor import Prediction, Predictor
from app.repository import HistoryItem, PredictionRepository, SavedPrediction


class ClassificationService:
    def __init__(self, predictor: Predictor, repo: PredictionRepository) -> None:
        self._predictor = predictor
        self._repo = repo

    def classify(self, filename: str, data: bytes) -> tuple[SavedPrediction, Prediction]:
        """load_image → predictor.predict → repo.save; ошибки пробрасывает доменными исключениями."""
        ...

    def history(self) -> list[HistoryItem]:
        ...
