"""Summarizer & Entity Extractor combined service — single LLM call for summary + entity extraction."""

import json
import logging
import re

from src.repositories import character_repo, glossary_repo
from src.services.extractor import (
    _clean_json_string,
    extract_entities_fuzzy,
    parse_extraction_output,
)
from src.services.llm_adapters import get_adapter

logger = logging.getLogger(__name__)

COMBINED_SUMMARY_EXTRACT_PROMPT = """You are a professional literary assistant specializing in novel translation.
Analyze the provided novel chapter text (and previous context summary, if provided) and perform TWO tasks in a single JSON response:
1. Provide a concise running plot summary of key events and character developments in this chapter (under 3 paragraphs).
2. Extract all newly introduced or mentioned character names and glossary terms/locations/organizations/techniques.

CRITICAL REQUIREMENT:
Respond ONLY with a strict valid JSON object matching this schema:
{
  "chapter_summary": "A concise summary of key plot events and character developments in this chapter.",
  "characters": [
    {
      "name": "Original Character Name",
      "translated_name": "Translated / Indonesian Character Name",
      "gender": "male | female | unknown",
      "speech_style": "polite | casual | archaic | rude",
      "notes": "Brief background or role"
    }
  ],
  "glossary": [
    {
      "term_source": "Original Term / Location / Item",
      "term_translation": "Translated / Indonesian Term",
      "notes": "Context note (e.g. location, magic item, faction)"
    }
  ]
}

Rules:
- Output ONLY the JSON object. Do not include markdown codeblocks or extra text outside JSON.
- "chapter_summary" must be formatted in clean Markdown.
- If no new characters or terms are found, return empty lists: "characters": [], "glossary": []."""


def _fix_raw_newlines_in_json(json_str: str) -> str:
    """Escape raw unescaped line breaks inside JSON string values so json.loads succeeds."""
    def replace_newlines(match):
        content = match.group(1)
        return '"' + content.replace('\r\n', '\\n').replace('\n', '\\n') + '"'

    return re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', replace_newlines, json_str, flags=re.DOTALL)


def clean_markdown_text(text: str | None) -> str:
    """Sanitize and unescape markdown text (e.g. convert literal '\\n' to real newlines, clean escaped quotes)."""
    if not text:
        return ""
    cleaned = str(text).strip()

    # Unescape literal \n if present
    if "\\n" in cleaned:
        cleaned = cleaned.replace("\\n", "\n")

    # Unescape quotes and tabs
    cleaned = cleaned.replace('\\"', '"').replace("\\'", "'").replace("\\t", "\t")

    # Strip markdown codeblock wrapper if summary itself was wrapped in ``` ... ```
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned


async def summarize_and_extract_chapter(
    *,
    translated_text: str,
    previous_summary: str | None,
    series_id: int,
    model: dict,
    platform: dict,
) -> dict:
    """Generate chapter plot summary AND extract entities in a single combined LLM call (Pass 2).

    Returns a dict containing:
      - chapter_summary (str)
      - extracted_characters (list)
      - extracted_terms (list)
      - extract_status (str: 'done' | 'failed')
    """
    user_prompt = "Analyze this newly translated chapter and return summary + extracted entities:\n"
    if previous_summary:
        user_prompt += f"\nPrevious Story Summary Context:\n{previous_summary}\n\n"
    user_prompt += f"\nNEW CHAPTER TEXT:\n{translated_text}"

    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    chapter_summary = ""
    extracted_chars = []
    extracted_terms = []
    extract_status = "done"
    raw_response = ""

    try:
        response_text = await adapter.call(
            system_prompt=COMBINED_SUMMARY_EXTRACT_PROMPT,
            user_prompt=user_prompt,
            model_name=model["name"],
            base_url=base_url,
            api_key=api_key,
        )
        raw_response = response_text

        # 1. Parse JSON output with robust newline escaping
        json_str = _clean_json_string(response_text)
        try:
            data = json.loads(json_str)
        except Exception:  # noqa: BLE001
            try:
                data = json.loads(_fix_raw_newlines_in_json(json_str))
            except Exception:  # noqa: BLE001
                data = None

        if isinstance(data, dict):
            chapter_summary = str(data.get("chapter_summary") or data.get("summary") or "").strip()
            extracted_chars, extracted_terms = extract_entities_fuzzy(data)
        else:
            # Fallback if JSON parsing fails: use Markdown fallback parser
            chapter_summary = response_text
            extracted_chars, extracted_terms = parse_extraction_output(response_text)

        if not chapter_summary:
            chapter_summary = response_text

    except Exception as exc:  # noqa: BLE001
        logger.warning("Combined summarize & extract call failed for series %d: %s. Using fallback.", series_id, exc)
        chapter_summary = "Summary of newly translated chapter text."
        extract_status = "failed"

    # Sanitize and unescape markdown text so it displays formatted
    chapter_summary = clean_markdown_text(chapter_summary)

    # 2. Instant Secondary Pass fallback parsing if JSON parsing returned 0 items
    if not extracted_chars and not extracted_terms and chapter_summary:
        c_sum, t_sum = parse_extraction_output(chapter_summary)
        extracted_chars.extend(c_sum)
        extracted_terms.extend(t_sum)

    # 3. Upsert extracted entities into SQLite DB
    char_count = 0
    term_count = 0

    if series_id > 0:
        for char in extracted_chars:
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
                char_count += 1

        for term in extracted_terms:
            t_src = term.get("term_source")
            t_trans = term.get("term_translation") or t_src
            if t_src and t_trans:
                await glossary_repo.upsert_term(
                    series_id=series_id,
                    term_source=str(t_src).strip(),
                    term_translation=str(t_trans).strip(),
                    notes=term.get("notes"),
                )
                term_count += 1

    logger.info(
        "Combined Pass 2 completed for series %d: Summary generated (%d chars), Extracted %d characters and %d glossary terms.",
        series_id, len(chapter_summary), char_count, term_count
    )

    return {
        "chapter_summary": chapter_summary,
        "extracted_characters": extracted_chars,
        "extracted_terms": extracted_terms,
        "extract_status": extract_status,
        "system_prompt": COMBINED_SUMMARY_EXTRACT_PROMPT,
        "user_prompt": user_prompt,
        "raw_response": raw_response,
    }


async def summarize_chapter(
    *,
    translated_text: str,
    previous_summary: str | None,
    model: dict,
    platform: dict,
) -> str:
    """Legacy helper for single summary call."""
    res = await summarize_and_extract_chapter(
        translated_text=translated_text,
        previous_summary=previous_summary,
        series_id=0,
        model=model,
        platform=platform,
    )
    return res["chapter_summary"]
