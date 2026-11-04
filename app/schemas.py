"""Pydantic-модели HTTP-ответов."""
from pydantic import BaseModel, ConfigDict, Field


class PredictResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    image_id: int
    prediction_id: int
    label: str = Field(serialization_alias="class")
    model_version: str


class HistoryItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    prediction_id: int
    image_id: int
    filename: str
    label: str = Field(serialization_alias="class")
    model_version: str
    created_at: str
