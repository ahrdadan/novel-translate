"""Job repository — CRUD for the jobs table (async job queue)."""

import json
from datetime import UTC, datetime

from src.database import get_db


async def create_job(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO jobs
           (series_id, chapter_number, status, force_translate, force_summary,
            extract, translation_model_ref, extraction_model_ref)
           VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)""",
        (
            data["series_id"],
            data["chapter_number"],
            int(data.get("force_translate", False)),
            int(data.get("force_summary", False)),
            int(data.get("extract", True)),
            json.dumps(data.get("translation_model_ref")) if data.get("translation_model_ref") else None,
            json.dumps(data.get("extraction_model_ref")) if data.get("extraction_model_ref") else None,
        ),
    )
    await db.commit()
    return await get_job_by_id(cursor.lastrowid)


async def get_job_by_id(job_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
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
    return job


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
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if series_id is not None:
        query += " AND series_id = ?"
        params.append(series_id)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ?"
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
        jobs.append(job)
    return jobs
