"""Сценарий с фейками: битое изображение не зовёт предсказатель, упавший предсказатель ничего не сохраняет."""
import pytest

from app.errors import InvalidImageError, PredictionError, StorageError
from app.predictor import Prediction, StubPredictor
from app.service import ClassificationService


class FakeRepo:
    def __init__(self, fail: bool = False) -> None:
        self.saved = []
        self.fail = fail

    def save(self, filename, prediction):
        if self.fail:
            raise StorageError("db is down")
        self.saved.append((filename, prediction))
        return type("Saved", (), {"image_id": 1, "prediction_id": 2})()


class SpyPredictor:
    def __init__(self) -> None:
        self.calls = 0

    def predict(self, image):
        self.calls += 1
        return Prediction("cat", "stub-v1")


class BrokenPredictor:
    def predict(self, image):
        raise RuntimeError("model crashed")


def test_classify_success(png_bytes):
    repo = FakeRepo()

    result = ClassificationService(StubPredictor(), repo).classify("cat.png", png_bytes)

    assert (result.image_id, result.prediction_id, result.label) == (1, 2, "cat")
    assert repo.saved == [("cat.png", Prediction("cat", "stub-v1"))]


def test_invalid_image_skips_predictor_and_db():
    predictor, repo = SpyPredictor(), FakeRepo()

    with pytest.raises(InvalidImageError):
        ClassificationService(predictor, repo).classify("x.png", b"not an image")

    assert predictor.calls == 0
    assert repo.saved == []


def test_broken_predictor_saves_nothing(png_bytes):
    repo = FakeRepo()

    with pytest.raises(PredictionError):
        ClassificationService(BrokenPredictor(), repo).classify("cat.png", png_bytes)

    assert repo.saved == []


def test_storage_error_propagates(png_bytes):
    with pytest.raises(StorageError):
        ClassificationService(StubPredictor(), FakeRepo(fail=True)).classify("cat.png", png_bytes)
