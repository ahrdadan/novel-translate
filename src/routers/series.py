"""Series router — CRUD + status + summary (PRD §6.3, §6.4)."""

from fastapi import APIRouter, HTTPException

from src.models.series import (
    SeriesCreate,
    SeriesResponse,
    SeriesStatusResponse,
    SeriesUpdate,
    SummaryUpdate,
)
from src.repositories import series_repo

router = APIRouter(prefix="/series", tags=["series"])


@router.post("", response_model=SeriesResponse, status_code=201)
async def create_series(body: SeriesCreate):
    data = body.model_dump(exclude_unset=True)
    return await series_repo.create_series(data)


@router.get("", response_model=list[SeriesResponse])
async def list_series():
    return await series_repo.get_all_series()


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(series_id: int):
    s = await series_repo.get_series_by_id(series_id)
    if not s:
        raise HTTPException(404, "Series not found")
    return s


@router.patch("/{series_id}", response_model=SeriesResponse)
async def update_series(series_id: int, body: SeriesUpdate):
    existing = await series_repo.get_series_by_id(series_id)
    if not existing:
        raise HTTPException(404, "Series not found")
    updates = body.model_dump(exclude_unset=True)
    return await series_repo.update_series(series_id, updates)


@router.delete("/{series_id}", status_code=204)
async def delete_series(series_id: int):
    deleted = await series_repo.delete_series(series_id)
    if not deleted:
        raise HTTPException(404, "Series not found")


# --- Status ---

@router.get("/{series_id}/status", response_model=SeriesStatusResponse)
async def get_series_status(series_id: int):
    status = await series_repo.get_series_status(series_id)
    if not status:
        raise HTTPException(404, "Series not found")
    return status


# --- Summary ---

@router.get("/{series_id}/summary")
async def get_series_summary(series_id: int):
    s = await series_repo.get_series_by_id(series_id)
    if not s:
        raise HTTPException(404, "Series not found")
    return {"series_id": series_id, "summary": s.get("summary", "")}


@router.post("/{series_id}/summary", response_model=SeriesResponse)
async def update_series_summary(series_id: int, body: SummaryUpdate):
    existing = await series_repo.get_series_by_id(series_id)
    if not existing:
        raise HTTPException(404, "Series not found")
    return await series_repo.update_series(series_id, {"summary": body.summary})
