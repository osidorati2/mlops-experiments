"""Заглушка отвечает cat / stub-v1; выбор реализации и подмена в приложении."""
import pytest

from app.main import create_app
from app.predictor import Prediction, StubPredictor, build_predictor


def test_stub_returns_cat_and_version(image):
    assert StubPredictor().predict(image) == Prediction(label="cat", model_version="stub-v1")


def test_build_predictor_stub():
    assert isinstance(build_predictor("stub"), StubPredictor)


def test_build_predictor_unknown():
    with pytest.raises(ValueError):
        build_predictor("resnet")


def test_app_accepts_any_predictor(image):
    class DogPredictor:
        def predict(self, image):
            return Prediction(label="dog", model_version="test")

    app = create_app(predictor=DogPredictor())

    assert app.state.predictor.predict(image).label == "dog"
