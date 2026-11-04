"""Интерфейс предсказателя и заглушка; настоящая модель реализует тот же Protocol."""
from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class Prediction:
    label: str
    model_version: str


class Predictor(Protocol):
    def predict(self, image: Image.Image) -> Prediction: ...


class StubPredictor:
    """Всегда отвечает cat / stub-v1 — проверяем сервис вокруг модели."""

    def predict(self, image: Image.Image) -> Prediction:
        return Prediction(label="cat", model_version="stub-v1")
