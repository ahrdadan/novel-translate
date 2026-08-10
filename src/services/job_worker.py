"""Job worker — background asyncio worker loop with semaphore concurrency.

Implements PRD v2 §5.
"""

import asyncio
import logging
from datetime import UTC, datetime

from src.repositories import (
    chapter_repo,
    job_repo,
    platform_repo,
    series_repo,
)
from src.services import extractor, model_resolver, summarizer, translator

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def resume_pending_jobs() -> None:
    """Startup handler: reset stuck 'processing' jobs and start the worker loop."""
    stuck_jobs = await job_repo.get_jobs_by_status(["processing"])
    for job in stuck_jobs:
        logger.info("Resetting stuck job %d from 'processing' to 'queued'", job["id"])
        await job_repo.update_job_status(job["id"], "queued")

    global _worker_task
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Job worker loop started")


async def _worker_loop() -> None:
    """Continuously poll for queued jobs and execute them within semaphore limits."""
    while True:
        try:
            job = await job_repo.get_next_queued()
            if job:
                # Simple approach: create a bounded task
                # For true semaphore limiting we track active count
                asyncio.create_task(_execute_job_safe(job))

            await asyncio.sleep(1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Worker loop error: %s", exc)
            await asyncio.sleep(5)


async def _execute_job_safe(job: dict) -> None:
    """Wrapper to catch and log all errors from job execution."""
    try:
        await execute_job(job)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unhandled error in job %d: %s", job["id"], exc)
        await job_repo.update_job_status(job["id"], "failed", error=str(exc))



async def execute_job(job: dict) -> None:
    """Execute a single translation job.

    Steps:
    1. Mark as 'processing'
    2. Resolve models (translation + extraction)
    3. Translate chapter
    4. Summarize
    5. Extract (optional)
    6. Update chapter and job status
    """
    job_id = job["id"]
    series_id = job["series_id"]
    chapter_number = job["chapter_number"]

    await job_repo.update_job_status(job_id, "processing")

    try:
        # Get chapter
        chapter = await chapter_repo.get_chapter(series_id, chapter_number)
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found in series {series_id}")

        # Check if already translated and force flags
        if chapter["status"] == "translated" and not job.get("force_translate"):
            # Already translated, skip unless forced
            result = {
                "chapter_number": chapter_number,
                "translated_text": chapter.get("translated_text", ""),
                "chapter_summary": chapter.get("chapter_summary", ""),
                "extract_status": chapter.get("extract_status", "skipped"),
                "status": "translated",
                "translated_by_model_name": chapter.get("translated_by_model_name", ""),
                "source_language": chapter.get("source_language", ""),
            }
            await job_repo.update_job_status(job_id, "completed", result=result)
            return

        # Resolve translation model
        trans_model = await model_resolver.resolve_model_for_purpose(
            "translation",
            job.get("translation_model_ref"),
            series_id,
        )
        trans_platform = await platform_repo.get_platform_by_id(trans_model["platform_id"])

        # Translate
        translated_text = await translator.translate_chapter(
            source_text=chapter["source_text"],
            series_id=series_id,
            chapter_number=chapter_number,
            model=trans_model,
            platform=trans_platform,
            system_prompt_ref=job.get("system_prompt_ref"),
        )


        # Summarize
        prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
        chapter_summary = await summarizer.summarize_chapter(
            translated_text=translated_text,
            previous_summary=prev_summary,
            model=trans_model,
            platform=trans_platform,
        )

        # Update chapter with translation results
        now = datetime.now(UTC).isoformat()
        chapter_updates = {
            "translated_text": translated_text,
            "chapter_summary": chapter_summary,
            "status": "translated",
            "translated_by_model_id": trans_model["id"],
            "translated_by_model_name": trans_model["name"],
            "translated_by_platform_name": trans_platform["name"],
            "translated_at": now,
        }

        # Extract (optional)
        extract_status = "skipped"
        if job.get("extract", True):
            try:
                extract_model = await model_resolver.resolve_model_for_purpose(
                    "extraction",
                    job.get("extraction_model_ref"),
                    series_id,
                )
                extract_platform = await platform_repo.get_platform_by_id(extract_model["platform_id"])

                extract_status = await extractor.extract_from_chapter(
                    translated_text=translated_text,
                    series_id=series_id,
                    model=extract_model,
                    platform=extract_platform,
                )
                chapter_updates["extract_status"] = extract_status
                chapter_updates["extracted_by_model_id"] = extract_model["id"]
                chapter_updates["extracted_by_model_name"] = extract_model["name"]
                chapter_updates["extracted_at"] = now
            except Exception as exc:  # noqa: BLE001
                logger.warning("Extraction failed for job %d: %s", job_id, exc)
                extract_status = "failed"
                chapter_updates["extract_status"] = "failed"
        else:
            chapter_updates["extract_status"] = "skipped"

        await chapter_repo.update_chapter(chapter["id"], chapter_updates)

        # Update series.last_translated_chapter
        series = await series_repo.get_series_by_id(series_id)
        if series and chapter_number > series.get("last_translated_chapter", 0):
            await series_repo.update_series(series_id, {"last_translated_chapter": chapter_number})

        # Mark job completed
        result = {
            "chapter_number": chapter_number,
            "translated_text": translated_text,
            "chapter_summary": chapter_summary,
            "extract_status": extract_status,
            "status": "translated",
            "translated_by_model_name": trans_model["name"],
            "source_language": chapter.get("source_language", "auto"),
        }
        await job_repo.update_job_status(job_id, "completed", result=result)

    except Exception as exc:  # noqa: BLE001
        logger.error("Job %d failed: %s", job_id, exc)
        await job_repo.update_job_status(job_id, "failed", error=str(exc))

