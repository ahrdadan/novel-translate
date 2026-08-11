"""Character schemas."""

from datetime import datetime

from pydantic import BaseModel


class CharacterCreate(BaseModel):
    name: str
    translated_name: str | None = None
    gender: str | None = None
    speech_style: str | None = None
    notes: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = None
    translated_name: str | None = None
    gender: str | None = None
    speech_style: str | None = None
    notes: str | None = None


class CharacterResponse(BaseModel):
    id: int
    series_id: int
    name: str
    translated_name: str | None = None
    gender: str | None = None
    speech_style: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
