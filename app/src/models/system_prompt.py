"""System prompt Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SystemPromptCreate(BaseModel):
    name: str
    prompt_text: str = Field(..., alias="promptText")
    is_default: bool = Field(False, alias="isDefault")

    model_config = {"populate_by_name": True}


class SystemPromptUpdate(BaseModel):
    name: str | None = None
    prompt_text: str | None = Field(None, alias="promptText")
    is_default: bool | None = Field(None, alias="isDefault")

    model_config = {"populate_by_name": True}


class SystemPromptReference(BaseModel):
    system_prompt_id: int | None = Field(None, alias="systemPromptId")
    id: int | None = None
    name: str | None = None
    prompt_text: str | None = Field(None, alias="promptText")

    model_config = {"populate_by_name": True}



class SystemPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prompt_text: str
    is_default: bool
    created_at: str | datetime | None = None
    updated_at: str | datetime | None = None
