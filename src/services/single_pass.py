"""Single-pass translation service — single LLM call for translation, summarization, and entity extraction.

Implements single_pass execution strategy.
"""

import json
import logging

from src.repositories import chapter_repo, character_repo, glossary_repo
from src.services import prompt_resolver
from src.services.extractor import _clean_json_string, extract_entities_fuzzy
from src.services.llm_adapters import get_adapter
from src.services.translator import (
    DEFAULT_SYSTEM_PROMPT,
    _build_context_prompt,
    _build_glossary_prompt,
)

logger = logging.getLogger(__name__)

SINGLE_PASS_INSTRUCTION = """

CRITICAL INSTRUCTION FOR SINGLE PASS MODE:
You must translate the chapter and provide a chapter summary and entity extraction.
Respond ONLY with a valid JSON object strictly matching this schema (no extra explanation or text outside JSON):
{
  "translation": "The full translated chapter text formatted in valid Markdown",
  "chapter_summary": "A concise summary of key plot events in this chapter (under 3 paragraphs)",
  "characters": [
    {"name": "Original Name", "translated_name": "Translated Name", "gender": "male/female/unknown", "notes": "brief description"}
  ],
  "glossary": [
    {"term_source": "Original Term", "term_translation": "Translation", "notes": "context"}
  ]
}

Rules:
- "translation" must contain the COMPLETE chapter translation without summarizing or omitting any paragraphs.
- In "characters", extract any newly introduced character names. If none, return an empty array [].
- In "glossary", extract any unique new terms, items, locations, or techniques. If none, return an empty array [].
- Keep the JSON strictly valid and parseable.
"""


async def translate_chapter_single_pass(
    *,
    source_text: str,
    series_id: int,
    chapter_number: float,
    model: dict,
    platform: dict,
    system_prompt_ref: dict | None = None,
) -> dict:
    """Execute translation, summarization, and extraction in a single LLM call.

    Returns a dict containing:
      - translated_text (str)
      - chapter_summary (str)
      - extract_status (str: 'done' | 'failed')
      - extracted_characters (list)
      - extracted_terms (list)
    """
    # 1. Resolve base system prompt
    prompt_obj = await prompt_resolver.resolve_system_prompt_for_series(
        system_prompt_ref, series_id
    )
    base_prompt_text = prompt_obj.get("prompt_text") or DEFAULT_SYSTEM_PROMPT

    # 2. Build system prompt with single-pass instruction and glossary
    system_prompt = base_prompt_text + SINGLE_PASS_INSTRUCTION

    glossary_terms = await glossary_repo.get_terms_by_series(series_id)
    glossary_prompt = _build_glossary_prompt(glossary_terms)
    if glossary_prompt:
        system_prompt += glossary_prompt

    # 3. Build context prompt from previous chapter summary
    prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
    context_prompt = _build_context_prompt(prev_summary)

    user_prompt = ""
    if context_prompt:
        user_prompt += context_prompt
    user_prompt += f"\n\nCURRENT TEXT TO TRANSLATE:\n{source_text}"

    # 4. Call LLM via adapter
    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    response_text = await adapter.call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=model["name"],
        base_url=base_url,
        api_key=api_key,
    )

    # 5. Parse JSON output with robust regex extraction & fuzzy anti-typo parsing
    json_str = _clean_json_string(response_text)

    translated_text = ""
    chapter_summary = ""
    extract_status = "done"
    characters = []
    glossary = []

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            translated_text = str(data.get("translation") or data.get("translated_text") or "").strip()
            chapter_summary = str(data.get("chapter_summary") or data.get("summary") or "").strip()

        characters, glossary = extract_entities_fuzzy(data)

        # Fallback if translation was somehow empty
        if not translated_text:
            translated_text = response_text

        # Upsert extracted characters
        for char in characters:
            c_name = char.get("name")
            c_trans = char.get("translated_name") or c_name
            if c_name:
                await character_repo.upsert_character(
                    series_id=series_id,
                    name=str(c_name).strip(),
                    translated_name=str(c_trans).strip() if c_trans else None,
                    gender=char.get("gender", "unknown"),
                    speech_style=char.get("speech_style", "casual"),
                    notes=char.get("notes"),
                )

        # Upsert extracted glossary terms
        for term in glossary:
            t_src = term.get("term_source")
            t_trans = term.get("term_translation") or t_src
            if t_src and t_trans:
                await glossary_repo.upsert_term(
                    series_id=series_id,
                    term_source=str(t_src).strip(),
                    term_translation=str(t_trans).strip(),
                    notes=term.get("notes"),
                )

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse single-pass JSON response: %s", exc)
        extract_status = "failed"
        translated_text = response_text

    return {
        "translated_text": translated_text,
        "chapter_summary": chapter_summary,
        "extract_status": extract_status,
        "extracted_characters": characters,
        "extracted_terms": glossary,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": response_text,
    }
