"""Job schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: int
    series_id: int
    series_name: str | None = None
    chapter_number: float
    chapter_title: str | None = None
    status: str
    force_translate: bool = False
    force_summary: bool = False
    extract: bool = True
    result: dict[str, Any] | None = None
    error: str | None = None
    queue_position: int | None = None
    total_in_queue: int | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobCreatedResponse(BaseModel):
    """Returned when an async translate request creates a job."""
    mode: str = "async"
    job_id: int
    status: str = "queued"
    status_url: str
