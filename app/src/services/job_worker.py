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
    settings_repo,
)
from src.services import model_resolver, single_pass, summarizer, translator
from src.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


_worker_task: asyncio.Task | None = None
_semaphore: asyncio.Semaphore | None = None
_active_model_ids: set[int] = set()


async def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        settings = await settings_repo.get_settings()
        limit = settings.get("max_concurrent_jobs", 1)
        _semaphore = asyncio.Semaphore(limit)
    return _semaphore


async def resume_pending_jobs() -> None:
    """Startup handler: fail any old 'processing' or 'queued' jobs from previous run."""
    stuck_jobs = await job_repo.get_jobs_by_status(["processing", "queued"])
    for job in stuck_jobs:
        logger.info("Marking job %d as failed due to server restart", job["id"])
        await job_repo.update_job_status(job["id"], "failed", error="Aborted due to server restart")
        
        # Reset corresponding chapter status back to pending
        chapter = await chapter_repo.get_chapter(job["series_id"], job["chapter_number"])
        if chapter and chapter.get("status") in ("processing", "queued", "pending"):
            await chapter_repo.update_chapter(chapter["id"], {"status": "pending"})

    global _worker_task
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Job worker loop started")


async def _worker_loop() -> None:
    """Continuously poll for queued jobs and execute them within semaphore limits."""
    semaphore = await get_semaphore()
    tick = 0
    while True:
        try:
            tick += 1
            if tick % 60 == 0:
                recovered = await job_repo.reset_stuck_jobs(timeout_minutes=15)
                if recovered:
                    logger.warning("Auto-failed %d stuck processing jobs (timeout)", len(recovered))

            if tick % 3600 == 0:
                cleaned = await job_repo.cleanup_old_completed_jobs(days=7)
                if cleaned > 0:
                    logger.info("Auto-cleaned %d old completed jobs", cleaned)

            settings = await settings_repo.get_settings()
            if settings.get("is_paused"):
                await asyncio.sleep(5)
                continue

            if not semaphore.locked():
                allow_diff = settings.get("allow_concurrent_different_models", False)
                job_to_run = None
                trans_model_id_to_track = None

                if allow_diff:
                    queued_jobs = await job_repo.get_queued_jobs_ordered(limit=10)
                    for qj in queued_jobs:
                        try:
                            # fast resolve model for this job to check its id
                            trans_model = await model_resolver.resolve_model_for_purpose(
                                "translation",
                                qj.get("translation_model_ref"),
                                qj["series_id"]
                            )
                            if trans_model["id"] not in _active_model_ids:
                                claimed = await job_repo.claim_specific_job(qj["id"])
                                if claimed:
                                    job_to_run = claimed
                                    trans_model_id_to_track = trans_model["id"]
                                break
                        except Exception as e:
                            logger.error("Failed resolving model for job %d during queue peek: %s", qj["id"], e)
                else:
                    job_to_run = await job_repo.claim_next_queued()
                
                if job_to_run:
                    if trans_model_id_to_track:
                        _active_model_ids.add(trans_model_id_to_track)
                    asyncio.create_task(_execute_job_with_semaphore(job_to_run, semaphore, trans_model_id_to_track))

            await asyncio.sleep(1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Worker loop error: %s", exc)
            await asyncio.sleep(5)


async def _execute_job_with_semaphore(job: dict, semaphore: asyncio.Semaphore, tracked_model_id: int | None = None) -> None:
    async with semaphore:
        await _execute_job_safe(job, tracked_model_id)


async def _execute_job_safe(job: dict, tracked_model_id: int | None = None) -> None:
    """Wrapper to catch and log all errors from job execution."""
    try:
        await execute_job(job)
    except BaseException as exc:
        logger.error("Unhandled error in job %d: %s", job["id"], exc)
        try:
            await job_repo.update_job_status(job["id"], "failed", error=str(exc))
            await ws_manager.broadcast({
                "type": "job_failed",
                "job_id": job["id"],
                "series_id": job.get("series_id"),
                "chapter_number": job.get("chapter_number"),
                "status": "failed",
                "error": str(exc),
                "message": f"Job #{job['id']} failed: {exc}",
            })
        except Exception as inner_exc:  # noqa: BLE001
            logger.error("Failed to update status for job %d: %s", job["id"], inner_exc)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        if tracked_model_id and tracked_model_id in _active_model_ids:
            _active_model_ids.discard(tracked_model_id)



async def execute_job(job: dict) -> None:
    """Execute a single translation job with real-time WebSocket event broadcasts."""
    job_id = job["id"]
    series_id = job["series_id"]
    chapter_number = job["chapter_number"]

    await ws_manager.broadcast({
        "type": "job_started",
        "job_id": job_id,
        "series_id": series_id,
        "chapter_number": chapter_number,
        "stage": "starting",
        "message": f"🚀 Job #{job_id} started processing (Chapter #{chapter_number})...",
    })

    try:
        # Get series and chapter info for rich progress messaging
        series = await series_repo.get_series_by_id(series_id)
        series_name = series.get("name") if series else f"Series #{series_id}"

        chapter = await chapter_repo.get_chapter(series_id, chapter_number)
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found in series {series_id}")

        chapter_title = chapter.get("title") or f"Chapter {chapter_number}"

        await ws_manager.broadcast({
            "type": "job_started",
            "job_id": job_id,
            "series_id": series_id,
            "series_name": series_name,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "stage": "starting",
            "message": f"🚀 Job #{job_id} started processing for '{series_name}' — Chapter #{chapter_number}: '{chapter_title}'",
        })

        # Set chapter status to processing
        await chapter_repo.update_chapter(chapter["id"], {"status": "processing"})

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
            await ws_manager.broadcast({
                "type": "job_completed",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "status": "completed",
                "message": f"✅ Job #{job_id} skipped (already translated).",
            })
            return

        # Resolve translation model
        await ws_manager.broadcast({
            "type": "stage_update",
            "job_id": job_id,
            "series_id": series_id,
            "series_name": series_name,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "stage": "resolving_model",
            "message": f"⚙️ Resolving translation model configuration for '{series_name}' Chapter #{chapter_number}...",
        })
        trans_model = await model_resolver.resolve_model_for_purpose(
            "translation",
            job.get("translation_model_ref"),
            series_id,
        )
        trans_platform = await platform_repo.get_platform_by_id(trans_model["platform_id"])

        if job.get("strategy") == "single_pass":
            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "translating_single_pass",
                "message": f"✍️ Single-pass translating Chapter #{chapter_number} using '{trans_model['name']}'...",
            })
            res = await single_pass.translate_chapter_single_pass(
                source_text=chapter["source_text"],
                series_id=series_id,
                chapter_number=chapter_number,
                model=trans_model,
                platform=trans_platform,
                system_prompt_ref=job.get("system_prompt_ref"),
            )
            translated_text = res["translated_text"]
            chapter_summary = res["chapter_summary"]
            extract_status = res["extract_status"]
        else:
            async def _on_trans_progress(data: dict) -> None:
                await ws_manager.broadcast({
                    "type": "stage_progress",
                    "job_id": job_id,
                    "series_id": series_id,
                    "series_name": series_name,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "stage": "translating",
                    "substage": data.get("substage"),
                    "chunk": data.get("chunk"),
                    "total_chunks": data.get("total_chunks"),
                    "paragraph_start": data.get("paragraph_start"),
                    "paragraph_end": data.get("paragraph_end"),
                    "total_paragraphs": data.get("total_paragraphs"),
                    "message": data.get("message"),
                })

            # 1. Translate
            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "translating",
                "message": f"✍️ Translating Chapter #{chapter_number} with '{trans_model['name']}' ({trans_platform['name']})...",
            })
            translated_text = await translator.translate_chapter(
                source_text=chapter["source_text"],
                series_id=series_id,
                chapter_number=chapter_number,
                model=trans_model,
                platform=trans_platform,
                system_prompt_ref=job.get("system_prompt_ref"),
                progress_callback=_on_trans_progress,
            )

            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "translating_complete",
                "message": f"✅ Translation of Chapter #{chapter_number} completed. Proceeding to plot summary...",
            })

            # Pause briefly to prevent rate limits on back-to-back LLM calls
            await asyncio.sleep(1.0)

            # 2. Summarize (using summarize_model_ref if provided, otherwise trans_model)
            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "summarizing",
                "message": f"📝 Updating plot summary memory for Chapter #{chapter_number}...",
            })
            await asyncio.sleep(0.1)
            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "extracting",
                "message": "🔍 Extracting new entities and glossary terms...",
            })
            sum_model = trans_model
            sum_platform = trans_platform
            if job.get("summarize_model_ref"):
                try:
                    sum_model = await model_resolver.resolve_model_for_purpose(
                        "summarization",
                        job.get("summarize_model_ref"),
                        series_id,
                    )
                    sum_platform = await platform_repo.get_platform_by_id(sum_model["platform_id"])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Summarization model resolution failed for job %d: %s", job_id, exc)

            prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
            try:
                sum_res = await summarizer.summarize_and_extract_chapter(
                    translated_text=translated_text,
                    previous_summary=prev_summary,
                    series_id=series_id,
                    model=sum_model,
                    platform=sum_platform,
                )
                chapter_summary = sum_res["chapter_summary"]
                extract_status = sum_res["extract_status"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Combined summarize & extract call failed for job %d: %s. Using fallback summary.", job_id, exc)
                chapter_summary = f"Summary for Chapter #{chapter_number} ({chapter_title})."
                extract_status = "failed"

            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "summarizing_complete",
                "message": f"✅ Plot summary updated for Chapter #{chapter_number}.",
            })

            await ws_manager.broadcast({
                "type": "stage_update",
                "job_id": job_id,
                "series_id": series_id,
                "series_name": series_name,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "stage": "extracting_complete",
                "message": f"✅ Entity extraction finished (status: {extract_status}).",
            })

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
            "extract_status": extract_status,
        }

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

        await ws_manager.broadcast({
            "type": "job_completed",
            "job_id": job_id,
            "series_id": series_id,
            "series_name": series_name,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "status": "completed",
            "message": f"🎉 Chapter #{chapter_number} translated successfully by '{trans_model['name']}'!",
        })

    except Exception as exc:  # noqa: BLE001
        logger.error("Job %d failed: %s", job_id, exc)
        await job_repo.update_job_status(job_id, "failed", error=str(exc))
        
        error_str = str(exc).lower()
        if any(keyword in error_str for keyword in ["429", "401", "403", "insufficient_quota", "rate limit"]):
            logger.critical("API Quota/Auth Error detected. Auto-pausing global queue.")
            await settings_repo.update_settings({"is_paused": 1})
            await ws_manager.broadcast({
                "type": "system_paused",
                "message": f"System Auto-Paused due to API Error on Job #{job_id}. Please check API Key and Resume.",
            })
        try:
            ch = await chapter_repo.get_chapter(series_id, chapter_number)
            if ch:
                await chapter_repo.update_chapter(ch["id"], {"status": "failed", "extract_status": "failed", "error": str(exc)})
        except Exception:  # noqa: BLE001, S110
            pass

        await ws_manager.broadcast({
            "type": "job_failed",
            "job_id": job_id,
            "series_id": series_id,
            "series_name": series_name if 'series_name' in locals() else f"Series #{series_id}",
            "chapter_number": chapter_number,
            "chapter_title": chapter_title if 'chapter_title' in locals() else f"Chapter #{chapter_number}",
            "status": "failed",
            "error": str(exc),
            "message": f"❌ Job #{job_id} (Chapter #{chapter_number}) failed: {exc}",
        })

