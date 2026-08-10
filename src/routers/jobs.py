"""Jobs router — GET /jobs/{id}, GET /jobs (PRD §6.7)."""

from fastapi import APIRouter, HTTPException

from src.models.job import JobResponse
from src.repositories import job_repo

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    series_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
):
    return await job_repo.list_jobs(series_id=series_id, status=status, limit=limit)
