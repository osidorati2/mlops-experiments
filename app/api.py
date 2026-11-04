"""HTTP-слой: принимает запросы, зовёт сервис, мапит доменные ошибки в коды ответа."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.schemas import HistoryItemResponse, PredictResponse
from app.service import ClassificationService

router = APIRouter()


def get_service() -> ClassificationService:
    """Зависимость FastAPI; в тестах подменяется через app.dependency_overrides."""
    ...


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/predict", response_model=PredictResponse, response_model_by_alias=True)
async def predict(file: UploadFile, service: ClassificationService = Depends(get_service)):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/predictions", response_model=list[HistoryItemResponse], response_model_by_alias=True)
def predictions(service: ClassificationService = Depends(get_service)):
    raise HTTPException(status_code=501, detail="Not implemented yet")
