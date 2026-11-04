"""Запросы из sql/queries.sql на фиксированном наборе sql/seed.sql дают заранее записанные результаты."""
from pathlib import Path

import pytest

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@pytest.fixture
def results(conn):
    conn.executescript((SQL_DIR / "seed.sql").read_text())
    queries = [q for q in (SQL_DIR / "queries.sql").read_text().split(";") if "SELECT" in q]
    return [[tuple(row) for row in conn.execute(q)] for q in queries]


def test_three_queries(results):
    assert len(results) == 3


def test_history_join(results):
    assert results[0] == [
        (4, 1, "cat.png", "cat", "resnet-v1", "2026-11-01T10:15:00+00:00"),
        (3, 3, "cat.png", "cat", "stub-v1", "2026-11-01T10:10:00+00:00"),
        (2, 2, "dog.jpg", "dog", "resnet-v1", "2026-11-01T10:05:00+00:00"),
        (1, 1, "cat.png", "cat", "stub-v1", "2026-11-01T10:00:00+00:00"),
    ]


def test_count_by_class(results):
    assert results[1] == [("cat", 3), ("dog", 1)]


def test_images_without_predictions(results):
    assert results[2] == [(4, "broken.png"), (5, "pending.jpg")]
