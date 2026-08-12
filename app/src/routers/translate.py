"""Translate router — POST /series/{id}/chapters/{n}/translate (PRD §6.6).

Supports sync (blocking) and async (job queue) modes.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.system_prompt import SystemPromptReference
from src.repositories import (
    chapter_repo,
    job_repo,
    platform_repo,
    series_repo,
    settings_repo,
)
from src.services import extractor, model_resolver, single_pass, summarizer, translator

router = APIRouter(prefix="/series/{series_id}/chapters/{chapter_number}", tags=["translate"])


class ModelReference(BaseModel):
    """Flexible model reference: either model_id or inline platform with models array."""
    model_id: int | None = Field(None, alias="modelId")
    platform: dict | None = None
    model: dict | None = None
    models: list[dict] | None = None

    model_config = {"populate_by_name": True}


class TranslateRequest(BaseModel):
    mode: str = "sync"  # sync | async
    strategy: str = "pipeline"  # pipeline | single_pass
    force_translate: bool = Field(False, alias="forceTranslate")
    force_summary: bool = Field(False, alias="forceSummary")
    extract: bool = True
    translation_model: ModelReference | None = Field(None, alias="translationModel")
    summarize_model: ModelReference | None = Field(None, alias="summarizeModel")
    extraction_model: ModelReference | None = Field(None, alias="extractionModel")
    system_prompt: SystemPromptReference | None = Field(None, alias="systemPrompt")
    llm_timeout: int | None = Field(None, alias="llmTimeout")
    max_tokens: int | None = Field(None, alias="maxTokens")

    model_config = {"populate_by_name": True}


@router.post("/translate")
async def translate_chapter(
    series_id: int,
    chapter_number: float,
    body: TranslateRequest | None = None,
):
    """Translate a chapter — sync (blocking) or async (job queue)."""
    if body is None:
        body = TranslateRequest()

    # Validate chapter exists
    chapter = await chapter_repo.get_chapter(series_id, chapter_number)
    if not chapter:
        raise HTTPException(404, f"Chapter {chapter_number} not found in series {series_id}")

    # Check if already translated (and force flags)
    if chapter["status"] == "translated" and not body.force_translate:
        raise HTTPException(
            409,
            f"Chapter {chapter_number} is already translated. "
            "Set force_translate=true to re-translate.",
        )

    # Build model & prompt refs as dicts for resolution/storage
    trans_ref = _model_ref_to_dict(body.translation_model) if body.translation_model else None
    summarize_ref = _model_ref_to_dict(body.summarize_model) if body.summarize_model else None
    extract_ref = _model_ref_to_dict(body.extraction_model) if body.extraction_model else None
    prompt_ref = _prompt_ref_to_dict(body.system_prompt) if body.system_prompt else None

    if body.mode == "async":
        return await _handle_async(series_id, chapter_number, body, trans_ref, summarize_ref, extract_ref, prompt_ref)
    else:
        return await _handle_sync(series_id, chapter_number, chapter, body, trans_ref, summarize_ref, extract_ref, prompt_ref)


@router.post("/retranslate")
@router.post("/retry")
async def retranslate_chapter(
    series_id: int,
    chapter_number: float,
    body: TranslateRequest | None = None,
):
    """Re-translate or retry a chapter (forces re-translation even if previously failed or translated)."""
    if body is None:
        body = TranslateRequest()

    body.force_translate = True

    chapter = await chapter_repo.get_chapter(series_id, chapter_number)
    if not chapter:
        raise HTTPException(404, f"Chapter {chapter_number} not found in series {series_id}")

    # Reset chapter status to pending to clear previous failure state
    await chapter_repo.update_chapter(chapter["id"], {"status": "pending", "extract_status": "pending"})

    trans_ref = _model_ref_to_dict(body.translation_model) if body.translation_model else None
    summarize_ref = _model_ref_to_dict(body.summarize_model) if body.summarize_model else None
    extract_ref = _model_ref_to_dict(body.extraction_model) if body.extraction_model else None
    prompt_ref = _prompt_ref_to_dict(body.system_prompt) if body.system_prompt else None

    if body.mode == "async":
        return await _handle_async(series_id, chapter_number, body, trans_ref, summarize_ref, extract_ref, prompt_ref)
    else:
        return await _handle_sync(series_id, chapter_number, chapter, body, trans_ref, summarize_ref, extract_ref, prompt_ref)


def _model_ref_to_dict(ref: ModelReference | None) -> dict | None:
    if ref is None:
        return None
    if ref.model_id is not None:
        return {"model_id": ref.model_id}
    if ref.platform:
        res: dict = {"platform": ref.platform}
        if ref.model:
            res["model"] = ref.model
        if ref.models:
            res["models"] = ref.models
        return res
    if ref.model:
        return {"model": ref.model}
    if ref.models:
        return {"models": ref.models}
    return None


def _prompt_ref_to_dict(ref: SystemPromptReference | None) -> dict | None:
    if ref is None:
        return None
    if ref.system_prompt_id is not None:
        return {"system_prompt_id": ref.system_prompt_id}
    if ref.prompt_text:
        res = {"prompt_text": ref.prompt_text}
        if ref.name:
            res["name"] = ref.name
        return res
    return None


async def _handle_async(
    series_id: int,
    chapter_number: float,
    body: TranslateRequest,
    trans_ref: dict | None,
    summarize_ref: dict | None,
    extract_ref: dict | None,
    prompt_ref: dict | None,
) -> dict:
    """Create a job and return immediately."""
    job = await job_repo.create_job({
        "series_id": series_id,
        "chapter_number": chapter_number,
        "strategy": body.strategy,
        "force_translate": body.force_translate,
        "force_summary": body.force_summary,
        "extract": body.extract,
        "translation_model_ref": trans_ref,
        "summarize_model_ref": summarize_ref,
        "extraction_model_ref": extract_ref,
        "system_prompt_ref": prompt_ref,
        "llm_timeout": body.llm_timeout,
        "max_tokens": body.max_tokens,
    })
    return {
        "mode": "async",
        "job_id": job["id"],
        "status": "queued",
        "status_url": f"/api/v1/jobs/{job['id']}",
    }


async def _handle_sync(
    series_id: int,
    chapter_number: float,
    chapter: dict,
    body: TranslateRequest,
    trans_ref: dict | None,
    summarize_ref: dict | None,
    extract_ref: dict | None,
    prompt_ref: dict | None,
) -> dict:
    """Execute translation synchronously (blocking)."""
    # Resolve translation model
    trans_model = await model_resolver.resolve_model_for_purpose(
        "translation", trans_ref, series_id
    )
    trans_platform = await platform_repo.get_platform_by_id(trans_model["platform_id"])

    llm_timeout = body.llm_timeout
    max_tokens = body.max_tokens
    if llm_timeout is None or max_tokens is None:
        settings = await settings_repo.get_settings()
        if llm_timeout is None:
            llm_timeout = settings.get("default_llm_timeout") or 600
        if max_tokens is None:
            max_tokens = settings.get("default_max_tokens") or 64000

    if body.strategy == "single_pass":
        res = await single_pass.translate_chapter_single_pass(
            source_text=chapter["source_text"],
            series_id=series_id,
            chapter_number=chapter_number,
            model=trans_model,
            platform=trans_platform,
            system_prompt_ref=prompt_ref,
            llm_timeout=llm_timeout,
            max_tokens=max_tokens,
        )
        translated_text = res["translated_text"]
        chapter_summary = res["chapter_summary"]
        extract_status = res["extract_status"]
    else:
        # Pipeline strategy
        # 1. Translate
        translated_text = await translator.translate_chapter(
            source_text=chapter["source_text"],
            series_id=series_id,
            chapter_number=chapter_number,
            model=trans_model,
            platform=trans_platform,
            system_prompt_ref=prompt_ref,
            llm_timeout=llm_timeout,
            max_tokens=max_tokens,
        )

        # 2. Summarize (resolve summarize_model if provided, otherwise trans_model)
        sum_model = trans_model
        sum_platform = trans_platform
        if summarize_ref:
            try:
                resolved_sum_model = await model_resolver.resolve_model_for_purpose(
                    "summarization", summarize_ref, series_id
                )
                sum_platform = await platform_repo.get_platform_by_id(resolved_sum_model["platform_id"])
                sum_model = resolved_sum_model
            except HTTPException:
                pass

        prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
        chapter_summary = await summarizer.summarize_chapter(
            translated_text=translated_text,
            previous_summary=prev_summary,
            model=sum_model,
            platform=sum_platform,
        )

        # 3. Extract (optional)
        extract_status = "skipped"
        if body.extract:
            try:
                extract_model = await model_resolver.resolve_model_for_purpose(
                    "extraction", extract_ref, series_id
                )
                extract_platform = await platform_repo.get_platform_by_id(extract_model["platform_id"])

                extract_status = await extractor.extract_from_chapter(
                    translated_text=translated_text,
                    series_id=series_id,
                    model=extract_model,
                    platform=extract_platform,
                )
            except HTTPException:
                # No extraction model configured — skip extraction silently
                extract_status = "skipped"
        else:
            extract_status = "skipped"

    # Update chapter
    now = datetime.now(UTC).isoformat()
    chapter_updates: dict[str, Any] = {
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

    return {
        "mode": "sync",
        "strategy": body.strategy,
        "chapter_number": chapter_number,
        "status": "translated",
        "translated_text": translated_text,
        "chapter_summary": chapter_summary,
        "extract_status": extract_status,
        "translated_by_model_name": trans_model["name"],
        "source_language": chapter.get("source_language", "auto"),
    }

