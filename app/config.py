"""Настройки из окружения: путь к БД и выбор предсказателя."""
import os

DB_PATH = os.getenv("DB_PATH", "data/app.db")
PREDICTOR = os.getenv("PREDICTOR", "stub")
