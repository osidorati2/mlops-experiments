"""TestClient: /health, /predict, /predictions и коды ошибок через dependency_overrides."""
import sqlite3
from contextlib import closing

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
    assert count_rows(app.state.db, "predictions") == 0


def test_predict_without_file_returns_422():
    response = TestClient(create_app()).post("/predict")

    assert response.status_code == 422


def test_predict_saves_linked_records_in_real_sqlite(tmp_path, png_bytes):
    db_path = tmp_path / "app.db"
    client = TestClient(create_app(db_path=str(db_path)))

    body = client.post("/predict", files={"file": ("cat.png", png_bytes, "image/png")}).json()

    # Отдельное соединение видит только закоммиченные данные — так проверяем, что запись реально сохранена.
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT images.id, images.filename, predictions.id, predictions.class, predictions.model_version"
            " FROM predictions JOIN images ON images.id = predictions.image_id"
        ).fetchall()
    assert rows == [(body["image_id"], "cat.png", body["prediction_id"], "cat", "stub-v1")]


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
    assert count_rows(app.state.db, "images") == 0  # откатилась вместе с predictions
    assert count_rows(app.state.db, "predictions") == 0


def test_history_empty():
    response = TestClient(create_app()).get("/history")

    assert response.status_code == 200
    assert response.json() == []


def test_history_returns_saved_results_with_filenames(png_bytes):
    client = TestClient(create_app())
    saved = [
        client.post("/predict", files={"file": (name, png_bytes, "image/png")}).json()
        for name in ("cat.png", "dog.png")
    ]

    response = client.get("/history")

    assert response.status_code == 200
    items = response.json()
    assert [(i["prediction_id"], i["image_id"], i["filename"]) for i in items] == [
        (saved[1]["prediction_id"], saved[1]["image_id"], "dog.png"),  # новые сверху
        (saved[0]["prediction_id"], saved[0]["image_id"], "cat.png"),
    ]
    assert all(i["class"] == "cat" and i["model_version"] == "stub-v1" and i["created_at"] for i in items)
