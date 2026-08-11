"""Platform schemas."""

from datetime import datetime

from pydantic import BaseModel, Field
from src.models.model import ModelResponse


class PlatformCreateModelInput(BaseModel):
    name: str
    url: str | None = None


class PlatformCreate(BaseModel):
    name: str
    api_key: str | None = Field(None, alias="apiKey")
    api_type: str = Field("chat-completions", alias="apiType")
    models: list[PlatformCreateModelInput] | None = None

    model_config = {"populate_by_name": True}


class PlatformUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = Field(None, alias="apiKey")
    api_type: str | None = Field(None, alias="apiType")

    model_config = {"populate_by_name": True}


class PlatformResponse(BaseModel):
    id: int
    name: str
    api_key: str | None = None
    api_type: str
    models: list[ModelResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

