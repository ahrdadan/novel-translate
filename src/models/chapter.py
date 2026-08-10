"""Chapter schemas."""

from datetime import datetime

from pydantic import BaseModel


class ChapterCreate(BaseModel):
    chapter_number: float
    title: str | None = None
    source_text: str
    source_language: str | None = "auto"


class ChapterUpdate(BaseModel):
    title: str | None = None
    source_text: str | None = None
    source_language: str | None = None


class ChapterResponse(BaseModel):
    id: int
    series_id: int
    chapter_number: float
    title: str | None = None
    source_text: str
    source_language: str | None = None
    translated_text: str | None = None
    chapter_summary: str | None = None
    status: str
    extract_status: str
    translated_by_model_id: int | None = None
    translated_by_model_name: str | None = None
    translated_by_platform_name: str | None = None
    extracted_by_model_id: int | None = None
    extracted_by_model_name: str | None = None
    translated_at: datetime | None = None
    extracted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChapterListItem(BaseModel):
    """Lighter response for chapter listing (no full text)."""
    id: int
    series_id: int
    chapter_number: float
    title: str | None = None
    status: str
    extract_status: str
    source_language: str | None = None
    translated_by_model_name: str | None = None
    translated_at: datetime | None = None
    created_at: datetime | None = None


class ChapterContextResponse(BaseModel):
    """Context preview for a chapter (summary of previous chapters)."""
    chapter_number: float
    previous_summary: str | None = None
    glossary: list[dict] = []
    characters: list[dict] = []
