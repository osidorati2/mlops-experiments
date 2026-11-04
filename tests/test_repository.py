"""save пишет обе записи; сбой второй вставки откатывает первую; history делает JOIN."""
import pytest

from app.errors import StorageError
from app.predictor import Prediction
from app.repository import PredictionRepository
from tests.conftest import count_rows


def test_save_creates_image_and_prediction(conn):
    saved = PredictionRepository(conn).save("cat.png", Prediction("cat", "stub-v1"))

    row = conn.execute(
        "SELECT i.filename, p.class, p.model_version, p.created_at"
        " FROM predictions p JOIN images i ON i.id = p.image_id WHERE p.id = ?",
        (saved.prediction_id,),
    ).fetchone()
    assert tuple(row)[:3] == ("cat.png", "cat", "stub-v1")
    assert row["created_at"]


def test_same_filename_creates_new_records(conn):
    repo = PredictionRepository(conn)

    first = repo.save("cat.png", Prediction("cat", "stub-v1"))
    second = repo.save("cat.png", Prediction("cat", "stub-v1"))

    assert first.image_id != second.image_id
    assert count_rows(conn, "images") == 2


def test_failed_prediction_insert_rolls_back_image(conn):
    # class NOT NULL → вторая вставка падает уже после того, как images вставлен
    with pytest.raises(StorageError):
        PredictionRepository(conn).save("cat.png", Prediction(None, "stub-v1"))

    assert count_rows(conn, "images") == 0
    assert count_rows(conn, "predictions") == 0


def test_history_empty(conn):
    assert PredictionRepository(conn).history() == []


def test_history_joins_filenames_newest_first(conn):
    repo = PredictionRepository(conn)
    first = repo.save("cat.png", Prediction("cat", "stub-v1"))
    second = repo.save("dog.jpg", Prediction("cat", "stub-v1"))

    items = repo.history()

    assert [(i.prediction_id, i.image_id, i.filename) for i in items] == [
        (second.prediction_id, second.image_id, "dog.jpg"),
        (first.prediction_id, first.image_id, "cat.png"),
    ]
    assert items[0].label == "cat" and items[0].model_version == "stub-v1"
