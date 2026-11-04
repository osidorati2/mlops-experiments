"""Точка сборки: создаёт БД, предсказатель, сервис и FastAPI-приложение."""
from fastapi import FastAPI

from app import config, db
from app.api import router
from app.predictor import Predictor, build_predictor
from app.repository import PredictionRepository
from app.service import ClassificationService


def create_app(predictor: Predictor | None = None, db_path: str | None = None) -> FastAPI:
    """Единственное место, где выбирается реализация Predictor (заглушка/модель)."""
    app = FastAPI(title="Image classifier")
    app.state.predictor = predictor or build_predictor(config.PREDICTOR)
    app.state.db = db.connect(db_path or config.DB_PATH)
    db.init_schema(app.state.db)
    app.state.service = ClassificationService(app.state.predictor, PredictionRepository(app.state.db))
    app.include_router(router)
    return app


app = create_app()
