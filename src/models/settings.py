"""Settings schemas."""

from datetime import datetime

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    id: int = 1
    max_concurrent_jobs: int
    default_translation_model_id: int | None = None
    default_extraction_model_id: int | None = None
    default_system_prompt_id: int | None = None
    is_paused: bool = False
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    max_concurrent_jobs: int | None = None
    default_translation_model_id: int | None = None
    default_extraction_model_id: int | None = None
    default_system_prompt_id: int | None = None
    is_paused: bool | None = None
