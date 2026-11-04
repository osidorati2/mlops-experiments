"""TestClient: /health, /predict, /predictions и коды ошибок через dependency_overrides."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_valid_image(png_bytes):
    client = TestClient(create_app())

    response = client.post("/predict", files={"file": ("cat.png", png_bytes, "image/png")})

    assert response.status_code == 200
    assert response.json() == {"class": "cat", "model_version": "stub-v1"}


@pytest.mark.parametrize("data", [b"", b"just some text"])
def test_predict_invalid_file_returns_400(data):
    called = []

    class SpyPredictor:
        def predict(self, image):
            called.append(image)

    client = TestClient(create_app(predictor=SpyPredictor()))

    response = client.post("/predict", files={"file": ("fake.png", data, "image/png")})

    assert response.status_code == 400
    assert "detail" in response.json()
    assert called == []  # предсказатель не вызывался


def test_predict_without_file_returns_422():
    response = TestClient(create_app()).post("/predict")

    assert response.status_code == 422
