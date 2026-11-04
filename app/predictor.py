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


def build_predictor(name: str) -> Predictor:
    """Выбор реализации по имени из конфига; новую модель добавляем сюда."""
    if name == "stub":
        return StubPredictor()
    raise ValueError(f"Unknown predictor: {name!r}")
