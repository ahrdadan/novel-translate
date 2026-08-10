"""System prompt Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SystemPromptCreate(BaseModel):
    name: str
    prompt_text: str
    is_default: bool = False


class SystemPromptUpdate(BaseModel):
    name: str | None = None
    prompt_text: str | None = None
    is_default: bool | None = None


class SystemPromptReference(BaseModel):
    system_prompt_id: int | None = None
    name: str | None = None
    prompt_text: str | None = None


class SystemPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prompt_text: str
    is_default: bool
    created_at: str | datetime | None = None
    updated_at: str | datetime | None = None
