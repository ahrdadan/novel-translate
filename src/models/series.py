"""Series schemas."""

from datetime import datetime

from pydantic import BaseModel


class SeriesCreate(BaseModel):
    name: str
    original_title: str | None = None
    author: str | None = None
    title_alts: str | None = None
    description: str | None = None
    status: str = "ongoing"
    summary: str = ""
    translation_model_id: int | None = None
    extraction_model_id: int | None = None
    system_prompt_id: int | None = None


class SeriesUpdate(BaseModel):
    name: str | None = None
    original_title: str | None = None
    author: str | None = None
    title_alts: str | None = None
    description: str | None = None
    status: str | None = None
    summary: str | None = None
    translation_model_id: int | None = None
    extraction_model_id: int | None = None
    system_prompt_id: int | None = None


class SeriesResponse(BaseModel):
    id: int
    name: str
    original_title: str | None = None
    author: str | None = None
    title_alts: str | None = None
    description: str | None = None
    status: str
    summary: str
    translation_model_id: int | None = None
    extraction_model_id: int | None = None
    system_prompt_id: int | None = None
    last_translated_chapter: float
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SeriesStatusResponse(BaseModel):
    id: int
    name: str
    status: str
    last_translated_chapter: float
    total_chapters: int
    translated_chapters: int
    pending_chapters: int
    failed_chapters: int


class SummaryUpdate(BaseModel):
    summary: str


class SummaryGenerateRequest(BaseModel):
    model_id: int | None = None
