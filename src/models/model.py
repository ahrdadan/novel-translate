"""Model schemas (LLM models within a platform)."""

from datetime import datetime

from pydantic import BaseModel


class ModelCreate(BaseModel):
    name: str
    url: str | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    url: str | None = None


class ModelResponse(BaseModel):
    id: int
    platform_id: int
    name: str
    url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModelDetailResponse(ModelResponse):
    """Extended response including platform info for flat /models list."""
    platform_name: str | None = None
    platform_api_type: str | None = None
