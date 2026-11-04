"""HTTP-слой: принимает запросы, зовёт сервис, мапит доменные ошибки в коды ответа."""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.errors import InvalidImageError
from app.image_validation import load_image
from app.schemas import HistoryItemResponse
from app.service import ClassificationService

router = APIRouter()


def get_service() -> ClassificationService:
    """Зависимость FastAPI; в тестах подменяется через app.dependency_overrides."""
    ...


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


# TODO: после БД перейти на service.classify и PredictResponse (image_id, prediction_id).
@router.post("/predict")
async def predict(file: UploadFile, request: Request) -> dict:
    try:
        image = load_image(await file.read())
        prediction = request.app.state.predictor.predict(image)
        return {"class": prediction.label, "model_version": prediction.model_version}
    except InvalidImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/predictions", response_model=list[HistoryItemResponse], response_model_by_alias=True)
def predictions(service: ClassificationService = Depends(get_service)):
    raise HTTPException(status_code=501, detail="Not implemented yet")
