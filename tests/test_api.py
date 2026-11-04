"""TestClient: /health, /predict, /predictions и коды ошибок через dependency_overrides."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.predictor import Prediction
from tests.conftest import count_rows


def test_health():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_valid_image_is_saved(png_bytes):
    app = create_app()
    client = TestClient(app)

    response = client.post("/predict", files={"file": ("cat.png", png_bytes, "image/png")})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "image_id": body["image_id"],
        "prediction_id": body["prediction_id"],
        "class": "cat",
        "model_version": "stub-v1",
    }
    row = app.state.db.execute(
        "SELECT i.filename, p.class FROM predictions p JOIN images i ON i.id = p.image_id"
        " WHERE p.id = ? AND i.id = ?",
        (body["prediction_id"], body["image_id"]),
    ).fetchone()
    assert tuple(row) == ("cat.png", "cat")


@pytest.mark.parametrize("data", [b"", b"just some text"])
def test_predict_invalid_file_returns_400(data):
    called = []

    class SpyPredictor:
        def predict(self, image):
            called.append(image)

    app = create_app(predictor=SpyPredictor())
    client = TestClient(app)

    response = client.post("/predict", files={"file": ("fake.png", data, "image/png")})

    assert response.status_code == 400
    assert "detail" in response.json()
    assert called == []  # предсказатель не вызывался
    assert count_rows(app.state.db, "images") == 0


def test_predict_without_file_returns_422():
    response = TestClient(create_app()).post("/predict")

    assert response.status_code == 422


def test_predict_broken_predictor_returns_500_and_saves_nothing(png_bytes):
    class BrokenPredictor:
        def predict(self, image):
            raise RuntimeError("model crashed")

    app = create_app(predictor=BrokenPredictor())

    response = TestClient(app).post("/predict", files={"file": ("cat.png", png_bytes, "image/png")})

    assert response.status_code == 500
    assert count_rows(app.state.db, "images") == 0
    assert count_rows(app.state.db, "predictions") == 0


def test_predict_db_failure_returns_500_and_rolls_back(png_bytes):
    class NullLabelPredictor:  # class NOT NULL → вставка в predictions падает после images
        def predict(self, image):
            return Prediction(None, "stub-v1")

    app = create_app(predictor=NullLabelPredictor())

    response = TestClient(app).post("/predict", files={"file": ("cat.png", png_bytes, "image/png")})

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to save result"}
    assert count_rows(app.state.db, "images") == 0
