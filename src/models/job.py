"""Job schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: int
    series_id: int
    chapter_number: int
    status: str
    force_translate: bool = False
    force_summary: bool = False
    extract: bool = True
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobCreatedResponse(BaseModel):
    """Returned when an async translate request creates a job."""
    mode: str = "async"
    job_id: int
    status: str = "queued"
    status_url: str
