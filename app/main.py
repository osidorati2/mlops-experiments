"""Точка сборки: создаёт БД, предсказатель, сервис и FastAPI-приложение."""
from fastapi import FastAPI

from app.api import router


def create_app() -> FastAPI:
    """Единственное место, где выбирается реализация Predictor (заглушка/модель)."""
    app = FastAPI(title="Image classifier")
    app.include_router(router)
    return app


app = create_app()
