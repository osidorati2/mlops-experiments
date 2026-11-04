"""HTTP-слой: принимает запросы, зовёт сервис, мапит доменные ошибки в коды ответа."""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.errors import InvalidImageError, PredictionError, StorageError
from app.schemas import HistoryItemResponse, PredictResponse
from app.service import ClassificationService

router = APIRouter()


def get_service(request: Request) -> ClassificationService:
    """Зависимость FastAPI; в тестах подменяется через app.dependency_overrides."""
    return request.app.state.service


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Обычный def: FastAPI выполнит его в пуле потоков, и SQLite не заблокирует event loop.
@router.post("/predict", response_model=PredictResponse, response_model_by_alias=True)
def predict(file: UploadFile, service: ClassificationService = Depends(get_service)):
    try:
        result = service.classify(file.filename or "", file.file.read())
    except InvalidImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except PredictionError:
        raise HTTPException(status_code=500, detail="Prediction failed") from None
    except StorageError:
        raise HTTPException(status_code=500, detail="Failed to save result") from None
    return PredictResponse(
        image_id=result.image_id,
        prediction_id=result.prediction_id,
        label=result.label,
        model_version=result.model_version,
    )


@router.get("/predictions", response_model=list[HistoryItemResponse], response_model_by_alias=True)
def predictions(service: ClassificationService = Depends(get_service)):
    raise HTTPException(status_code=501, detail="Not implemented yet")
