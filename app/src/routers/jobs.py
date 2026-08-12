"""Jobs router — GET /jobs/{id}, GET /jobs (PRD §6.7)."""

from fastapi import APIRouter, HTTPException

from src.database import get_db
from src.models.job import JobResponse
from src.repositories import chapter_repo, job_repo
from src.services import job_worker
from src.services.ws_manager import ws_manager

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


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: int):
    """Retry a failed, processing, or completed job by re-queuing it."""
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    # Reset job status to queued, force_translate to 1, and clear error/result
    await job_repo.update_job_status(job_id, "queued", result=None, error=None)

    db = await get_db()
    await db.execute("UPDATE jobs SET force_translate = 1 WHERE id = ?", (job_id,))
    await db.commit()

    # Reset corresponding chapter status to pending
    chapter = await chapter_repo.get_chapter(job["series_id"], job["chapter_number"])
    if chapter:
        await chapter_repo.update_chapter(chapter["id"], {"status": "pending", "extract_status": "pending"})

    # Broadcast WebSocket notification
    await ws_manager.broadcast({
        "type": "job_created",
        "job_id": job_id,
        "series_id": job["series_id"],
        "chapter_number": job["chapter_number"],
        "message": f"🔄 Job #{job_id} re-queued for retry (Chapter #{job['chapter_number']}).",
    })

    return await job_repo.get_job_by_id(job_id)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: int):
    """Cancel a queued or processing job."""
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    cancelled_job = await job_repo.cancel_job(job_id)
    
    # Abort async task if running
    job_worker.abort_running_job(job_id)

    # Reset corresponding chapter status to failed or pending
    chapter = await chapter_repo.get_chapter(job["series_id"], job["chapter_number"])
    if chapter and chapter.get("status") == "processing":
        await chapter_repo.update_chapter(chapter["id"], {"status": "pending"})

    await ws_manager.broadcast({
        "type": "job_failed",
        "job_id": job_id,
        "series_id": job["series_id"],
        "chapter_number": job["chapter_number"],
        "status": "failed",
        "error": "Cancelled by user",
        "message": f"🚫 Job #{job_id} was cancelled by user.",
    })

    return cancelled_job


@router.post("/reset-stuck")
async def reset_stuck_jobs(timeout_minutes: int = 15):
    """Manually trigger reset for jobs stuck in processing state."""
    reset_jobs = await job_repo.reset_stuck_jobs(timeout_minutes=timeout_minutes)
    return {
        "status": "ok",
        "reset_count": len(reset_jobs),
        "reset_jobs": [j["id"] for j in reset_jobs],
    }


@router.post("/cancel-all")
async def cancel_all_jobs():
    """Cancel all queued and processing jobs at once."""
    jobs_to_cancel = await job_repo.get_jobs_by_status(["queued", "processing"])
    
    cancelled_count = 0
    for job in jobs_to_cancel:
        # Update job to failed
        await job_repo.cancel_job(job["id"])
        
        # Abort async task
        job_worker.abort_running_job(job["id"])
        
        # Reset chapter status
        chapter = await chapter_repo.get_chapter(job["series_id"], job["chapter_number"])
        if chapter and chapter.get("status") in ("processing", "queued", "pending"):
            await chapter_repo.update_chapter(chapter["id"], {"status": "pending", "error": None})
            
        cancelled_count += 1
        
    await ws_manager.broadcast({
        "type": "jobs_cancelled",
        "message": f"🚫 Dibatalkan {cancelled_count} job secara massal oleh pengguna.",
    })
    
    return {"status": "ok", "cancelled_count": cancelled_count}


@router.delete("/cleanup")
async def cleanup_jobs(status: str = "completed"):
    """Manually delete jobs by status (e.g. 'completed' or 'completed,failed')."""
    status_list = [s.strip().lower() for s in status.split(",") if s.strip()]
    if not status_list:
        raise HTTPException(400, "No valid status provided for cleanup")
        
    deleted_count = await job_repo.delete_jobs_by_status(status_list)
    return {
        "status": "ok",
        "deleted_count": deleted_count,
        "cleared_statuses": status_list
    }
