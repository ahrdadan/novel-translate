"""Unified Translate router — POST /translate-novel (All-in-One endpoint).

Allows clients to submit Series, Chapter (raw text or HTML), Platform, Model, 
and System Prompt in a single request. If Series or Chapter do not exist, 
they are created automatically on-the-fly.
"""

from fastapi import APIRouter, HTTPException

from src.html_parser import convert_html_to_md
from src.models.system_prompt import SystemPromptReference
from src.models.unified import ModelReferenceInput, UnifiedTranslateRequest
from src.repositories import chapter_repo, series_repo
from src.routers.translate import _handle_async, _handle_sync
from src.services import prompt_resolver

router = APIRouter(tags=["translate"])


def _model_ref_to_dict(ref: ModelReferenceInput | int | str | dict | None) -> dict | int | None:
    if ref is None:
        return None
    if isinstance(ref, (int, str)) and str(ref).isdigit():
        return {"model_id": int(ref)}
    if isinstance(ref, dict):
        return ref
    if isinstance(ref, ModelReferenceInput):
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


def _prompt_ref_to_dict(
    ref: SystemPromptReference | int | str | dict | None,
) -> dict | int | str | None:
    if ref is None:
        return None
    if isinstance(ref, (int, str)):
        return ref
    if isinstance(ref, dict):
        return ref
    if isinstance(ref, SystemPromptReference):
        if ref.system_prompt_id is not None:
            return {"system_prompt_id": ref.system_prompt_id}
        if ref.id is not None:
            return {"system_prompt_id": ref.id}
        res: dict = {}
        if ref.name:
            res["name"] = ref.name
        if ref.prompt_text:
            res["prompt_text"] = ref.prompt_text
        return res if res else None
    return None



@router.post("/translate-novel", status_code=200)
async def translate_novel_unified(body: UnifiedTranslateRequest):
    """All-in-one endpoint: create/resolve Series, Chapter, Platform, Model, and translate."""
    # 1. Resolve or Create Series
    series = None
    series_id_input = None
    series_name_input = None
    series_orig_title = None
    series_author = None
    series_desc = None

    if isinstance(body.series, (int, str)) and str(body.series).isdigit():
        series_id_input = int(body.series)
    elif isinstance(body.series, str):
        series_name_input = body.series
    elif hasattr(body.series, "id") or hasattr(body.series, "name"):
        series_id_input = body.series.id
        series_name_input = body.series.name
        series_orig_title = getattr(body.series, "original_title", None)
        series_author = getattr(body.series, "author", None)
        series_desc = getattr(body.series, "description", None)
    elif isinstance(body.series, dict):
        series_id_input = body.series.get("id")
        series_name_input = body.series.get("name")
        series_orig_title = body.series.get("original_title") or body.series.get("originalTitle")
        series_author = body.series.get("author")
        series_desc = body.series.get("description")

    if series_id_input is not None:
        series = await series_repo.get_series_by_id(series_id_input)
        if not series:
            raise HTTPException(404, f"Series with id {series_id_input} not found")
    elif series_name_input:
        series = await series_repo.get_series_by_name(series_name_input)
        if not series:
            series_data = {
                "name": series_name_input,
                "original_title": series_orig_title,
                "author": series_author,
                "description": series_desc,
            }
            series_data = {k: v for k, v in series_data.items() if v is not None}
            series = await series_repo.create_series(series_data)
    else:
        raise HTTPException(400, "Must specify series.id or series.name")

    series_id = series["id"]

    # 2. Resolve Chapter input details
    chapter_num_input = None
    chap_title_input = None
    chap_source_input = None
    chap_lang_input = "auto"

    if isinstance(body.chapter, (int, str)) and str(body.chapter).isdigit():
        chapter_num_input = int(body.chapter)
    elif hasattr(body.chapter, "chapter_number"):
        chapter_num_input = body.chapter.chapter_number
        chap_title_input = getattr(body.chapter, "title", None)
        chap_source_input = getattr(body.chapter, "source_text", None)
        chap_lang_input = getattr(body.chapter, "source_language", "auto")
    elif isinstance(body.chapter, dict):
        chapter_num_input = body.chapter.get("chapter_number") or body.chapter.get("chapterNumber")
        chap_title_input = body.chapter.get("title")
        chap_source_input = body.chapter.get("source_text") or body.chapter.get("sourceText")
        chap_lang_input = body.chapter.get("source_language") or body.chapter.get("sourceLanguage", "auto")

    if chapter_num_input is None:
        raise HTTPException(400, "Must specify chapter.chapterNumber")

    chapter = await chapter_repo.get_chapter(series_id, chapter_num_input)

    if chap_source_input:
        cleaned_text = convert_html_to_md(chap_source_input)
    else:
        cleaned_text = None

    if chapter:
        if cleaned_text:
            updates = {"source_text": cleaned_text}
            if chap_title_input:
                updates["title"] = chap_title_input
            chapter = await chapter_repo.update_chapter(chapter["id"], updates)
    else:
        if not cleaned_text:
            raise HTTPException(400, "source_text is required when creating a new chapter")
        chap_data = {
            "series_id": series_id,
            "chapter_number": chapter_num_input,
            "title": chap_title_input,
            "source_text": cleaned_text,
            "source_language": chap_lang_input,
            "status": "pending",
        }
        chapter = await chapter_repo.create_chapter(chap_data)

    # 3. Check Translation Status & Force Flags
    if chapter["status"] == "translated" and not body.force_translate:
        raise HTTPException(
            409,
            f"Chapter {chapter_num_input} in series '{series['name']}' is already translated. "
            "Set force_translate=true to re-translate.",
        )

    # 4. Build Model & Prompt References
    trans_ref = _model_ref_to_dict(body.translation_model)
    extract_ref = _model_ref_to_dict(body.extraction_model)
    prompt_ref_raw = _prompt_ref_to_dict(body.system_prompt)
    prompt_ref = None
    if prompt_ref_raw:
        prompt_obj = await prompt_resolver.resolve_or_create_system_prompt(prompt_ref_raw)
        prompt_ref = {"system_prompt_id": prompt_obj["id"]} if prompt_obj.get("id") else prompt_ref_raw

    # 5. Dispatch Execution Mode

    if body.mode == "async":
        result = await _handle_async(series_id, chapter_num_input, body, trans_ref, extract_ref, prompt_ref)
        result["series_id"] = series_id
        result["series_name"] = series["name"]
        return result
    else:
        result = await _handle_sync(series_id, chapter_num_input, chapter, body, trans_ref, extract_ref, prompt_ref)
        result["series_id"] = series_id
        result["series_name"] = series["name"]
        return result

