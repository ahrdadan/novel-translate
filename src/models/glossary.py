"""Glossary term schemas."""

from datetime import datetime

from pydantic import BaseModel


class GlossaryTermCreate(BaseModel):
    term_source: str
    term_translation: str
    notes: str | None = None


class GlossaryTermUpdate(BaseModel):
    term_source: str | None = None
    term_translation: str | None = None
    notes: str | None = None


class GlossaryTermResponse(BaseModel):
    id: int
    series_id: int
    term_source: str
    term_translation: str
    notes: str | None = None
    created_at: datetime | None = None
