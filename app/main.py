"""Точка сборки: создаёт БД, предсказатель, сервис и FastAPI-приложение."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Единственное место, где выбирается реализация Predictor (заглушка/модель)."""
    ...


app = create_app()
