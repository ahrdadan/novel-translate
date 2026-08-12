"""Settings schemas."""

from datetime import datetime

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    id: int = 1
    max_concurrent_jobs: int = 1
    default_translation_model_id: int | None = None
    default_extraction_model_id: int | None = None
    default_system_prompt_id: int | None = None
    is_paused: bool = False
    allow_concurrent_different_models: bool = False
    default_llm_timeout: int = 40000
    default_max_tokens: int = 64000
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    max_concurrent_jobs: int | None = None
    default_translation_model_id: int | None = None
    default_extraction_model_id: int | None = None
    default_system_prompt_id: int | None = None
    is_paused: bool | None = None
    allow_concurrent_different_models: bool | None = None
    default_llm_timeout: int | None = None
    default_max_tokens: int | None = None
