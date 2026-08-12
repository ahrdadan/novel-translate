"""Job repository — CRUD for the jobs table (async job queue)."""

import json
from datetime import UTC, datetime

from src.database import get_db


async def create_job(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO jobs
           (series_id, chapter_number, status, force_translate, force_summary,
            extract, translation_model_ref, extraction_model_ref, strategy, llm_timeout, max_tokens)
           VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["series_id"],
            data["chapter_number"],
            int(data.get("force_translate", False)),
            int(data.get("force_summary", False)),
            int(data.get("extract", True)),
            json.dumps(data.get("translation_model_ref")) if data.get("translation_model_ref") else None,
            json.dumps(data.get("extraction_model_ref")) if data.get("extraction_model_ref") else None,
            data.get("strategy", "pipeline"),
            data.get("llm_timeout"),
            data.get("max_tokens"),
        ),
    )
    await db.commit()
    return await get_job_by_id(cursor.lastrowid)


async def get_job_by_id(job_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT j.*, s.name as series_name, c.title as chapter_title 
           FROM jobs j
           LEFT JOIN series s ON j.series_id = s.id
           LEFT JOIN chapters c ON j.series_id = c.series_id AND j.chapter_number = c.chapter_number
           WHERE j.id = ?""",
        (job_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    job = dict(row)
    # Parse JSON fields
    if job.get("result"):
        job["result"] = json.loads(job["result"])
    if job.get("translation_model_ref"):
        job["translation_model_ref"] = json.loads(job["translation_model_ref"])
    if job.get("extraction_model_ref"):
        job["extraction_model_ref"] = json.loads(job["extraction_model_ref"])
    # Convert int booleans
    job["force_translate"] = bool(job.get("force_translate", 0))
    job["force_summary"] = bool(job.get("force_summary", 0))
    job["extract"] = bool(job.get("extract", 1))

    if job["status"] in ("queued", "processing"):
        q_info = await get_job_queue_info(job_id)
        job["queue_position"] = q_info["queue_position"]
        job["total_in_queue"] = q_info["total_in_queue"]

    if job["status"] == "processing" and job.get("started_at"):
        try:
            started = datetime.fromisoformat(job["started_at"])
            job["elapsed_seconds"] = int((datetime.now(UTC) - started).total_seconds())
        except Exception:  # noqa: BLE001, S110
            pass

    return job


async def get_job_queue_info(job_id: int) -> dict[str, int]:
    """Calculate the queue position of a job and total active queued/processing jobs."""
    db = await get_db()
    c_total = await db.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'processing')"
    )
    r_total = await c_total.fetchone()
    total_count = r_total[0] if r_total else 0

    c_pos = await db.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'processing') AND id <= ?",
        (job_id,),
    )
    r_pos = await c_pos.fetchone()
    queue_position = r_pos[0] if r_pos else 0

    return {
        "queue_position": queue_position,
        "total_in_queue": total_count,
    }


async def get_next_queued() -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
    )
    row = await cursor.fetchone()
    if not row:
        return None
    job = dict(row)
    if job.get("translation_model_ref"):
        job["translation_model_ref"] = json.loads(job["translation_model_ref"])
    if job.get("extraction_model_ref"):
        job["extraction_model_ref"] = json.loads(job["extraction_model_ref"])
    job["force_translate"] = bool(job.get("force_translate", 0))
    job["force_summary"] = bool(job.get("force_summary", 0))
    job["extract"] = bool(job.get("extract", 1))
    return job


async def claim_next_queued() -> dict | None:
    """Atomically select the next queued job and update its status to 'processing'."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
    )
    row = await cursor.fetchone()
    if not row:
        return None

    job_id = row["id"]
    now = datetime.now(UTC).isoformat()
    res = await db.execute(
        "UPDATE jobs SET status = 'processing', started_at = ? WHERE id = ? AND status = 'queued'",
        (now, job_id),
    )
    await db.commit()
    if res.rowcount == 0:
        return None

    return await get_job_by_id(job_id)


async def get_queued_jobs_ordered(limit: int = 10) -> list[dict]:
    """Get the next N queued jobs in order without claiming them."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT ?",
        (limit,)
    )
    rows = await cursor.fetchall()
    jobs = []
    for r in rows:
        job = dict(r)
        if job.get("translation_model_ref"):
            job["translation_model_ref"] = json.loads(job["translation_model_ref"])
        if job.get("extraction_model_ref"):
            job["extraction_model_ref"] = json.loads(job["extraction_model_ref"])
        job["force_translate"] = bool(job.get("force_translate", 0))
        job["force_summary"] = bool(job.get("force_summary", 0))
        job["extract"] = bool(job.get("extract", 1))
        jobs.append(job)
    return jobs


async def claim_specific_job(job_id: int) -> dict | None:
    """Atomically claim a specific queued job."""
    db = await get_db()
    now = datetime.now(UTC).isoformat()
    res = await db.execute(
        "UPDATE jobs SET status = 'processing', started_at = ? WHERE id = ? AND status = 'queued'",
        (now, job_id),
    )
    await db.commit()
    if res.rowcount == 0:
        return None

    return await get_job_by_id(job_id)


async def reset_stuck_jobs(timeout_minutes: int = 15) -> list[dict]:
    """Find jobs stuck in 'processing' for longer than timeout_minutes and reset to 'queued'."""
    stuck_jobs = await get_jobs_by_status(["processing"])
    reset_jobs = []
    now = datetime.now(UTC)

    for job in stuck_jobs:
        started_at_str = job.get("started_at")
        is_stuck = False
        if not started_at_str:
            is_stuck = True
        else:
            try:
                started_dt = datetime.fromisoformat(started_at_str)
                # Ensure timezone awareness match
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=UTC)
                
                job_timeout_seconds = job.get("llm_timeout")
                if job_timeout_seconds:
                    # Give an extra 5 minutes (300 seconds) buffer over the llm_timeout
                    timeout_sec = job_timeout_seconds + 300
                else:
                    timeout_sec = timeout_minutes * 60
                
                if (now - started_dt).total_seconds() > timeout_sec:
                    is_stuck = True
            except ValueError:
                is_stuck = True

        if is_stuck:
            await update_job_status(job["id"], "failed", error="Job timeout (stuck in processing)")
            
            # Reset chapter status back to pending and clear error
            chapter = await get_db() # We shouldn't import chapter_repo here due to circular dep, just execute raw sql
            await chapter.execute(
                "UPDATE chapters SET status = 'pending', error = NULL WHERE series_id = ? AND chapter_number = ? AND status = 'processing'",
                (job["series_id"], job["chapter_number"])
            )
            await chapter.commit()
            
            reset_jobs.append(job)

    return reset_jobs


async def cancel_job(job_id: int) -> dict | None:
    """Cancel a queued or processing job, marking it as failed."""
    job = await get_job_by_id(job_id)
    if not job:
        return None

    if job["status"] in ("completed", "failed"):
        return job

    await update_job_status(job_id, "failed", error="Cancelled by user")
    return await get_job_by_id(job_id)


async def update_job_status(
    job_id: int,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    db = await get_db()
    now = datetime.now(UTC).isoformat()
    if status == "processing":
        await db.execute(
            "UPDATE jobs SET status = ?, started_at = ? WHERE id = ?",
            (status, now, job_id),
        )
    elif status in ("completed", "failed"):
        await db.execute(
            "UPDATE jobs SET status = ?, result = ?, error = ?, completed_at = ? WHERE id = ?",
            (status, json.dumps(result) if result else None, error, now, job_id),
        )
    else:
        await db.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (status, job_id),
        )
    await db.commit()


async def get_jobs_by_status(statuses: list[str]) -> list[dict]:
    db = await get_db()
    placeholders = ", ".join(["?"] * len(statuses))
    cursor = await db.execute(
        f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY id",
        statuses,
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def list_jobs(
    series_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    db = await get_db()
    query = """
        SELECT j.*, s.name as series_name, c.title as chapter_title 
        FROM jobs j
        LEFT JOIN series s ON j.series_id = s.id
        LEFT JOIN chapters c ON j.series_id = c.series_id AND j.chapter_number = c.chapter_number
        WHERE 1=1
    """
    params = []
    if series_id is not None:
        query += " AND j.series_id = ?"
        params.append(series_id)
    if status is not None:
        status_list = [s.strip().lower() for s in status.split(",") if s.strip()]
        # Alias 'pending' -> 'queued' for user convenience
        status_list = ["queued" if s == "pending" else s for s in status_list]
        if len(status_list) == 1:
            query += " AND j.status = ?"
            params.append(status_list[0])
        elif len(status_list) > 1:
            placeholders = ", ".join(["?"] * len(status_list))
            query += f" AND j.status IN ({placeholders})"
            params.extend(status_list)
    query += " ORDER BY j.id DESC LIMIT ?"
    params.append(limit)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    jobs = []
    for r in rows:
        job = dict(r)
        if job.get("result"):
            job["result"] = json.loads(job["result"])
        job["force_translate"] = bool(job.get("force_translate", 0))
        job["force_summary"] = bool(job.get("force_summary", 0))
        job["extract"] = bool(job.get("extract", 1))

        if job["status"] in ("queued", "processing"):
            q_info = await get_job_queue_info(job["id"])
            job["queue_position"] = q_info["queue_position"]
            job["total_in_queue"] = q_info["total_in_queue"]

        if job["status"] == "processing" and job.get("started_at"):
            try:
                started = datetime.fromisoformat(job["started_at"])
                job["elapsed_seconds"] = int((datetime.now(UTC) - started).total_seconds())
            except Exception:  # noqa: BLE001, S110
                pass

        jobs.append(job)
    return jobs


async def cleanup_old_completed_jobs(days: int = 7) -> int:
    """Delete jobs with status 'completed' older than X days."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM jobs WHERE status = 'completed' AND completed_at < datetime('now', ?)",
        (f"-{days} days",)
    )
    await db.commit()
    return cursor.rowcount


async def delete_jobs_by_status(statuses: list[str]) -> int:
    """Manually delete jobs by a list of statuses (e.g. ['completed', 'failed'])."""
    if not statuses:
        return 0
    db = await get_db()
    placeholders = ", ".join(["?"] * len(statuses))
    cursor = await db.execute(
        f"DELETE FROM jobs WHERE status IN ({placeholders})",
        statuses
    )
    await db.commit()
    return cursor.rowcount
