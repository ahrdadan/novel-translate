"""Extractor service — extract characters and glossary terms from translated text via LLM."""

import asyncio
import json
import logging
import re
from typing import Any

from src.repositories import character_repo, glossary_repo
from src.services.llm_adapters import get_adapter

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a professional literary entity extractor for novel translation.
Analyze the provided novel chapter text (which may be translated or original source text) and extract ALL newly introduced or mentioned character names and glossary terms/locations/organizations/techniques.

CRITICAL REQUIREMENT:
Output ONLY a strict JSON object. Do not include markdown codeblocks, commentary, or conversational text.

Required JSON Structure:
{
  "characters": [
    {
      "name": "Original Character Name",
      "translated_name": "Translated/Indonesian Character Name",
      "gender": "male | female | unknown",
      "speech_style": "polite | casual | archaic | rude",
      "notes": "Brief background or role"
    }
  ],
  "glossary": [
    {
      "term_source": "Original Term / Location / Item",
      "term_translation": "Translated / Indonesian Term",
      "notes": "Context note (e.g. location, magic item, faction, technique)"
    }
  ]
}

Rules:
1. Extract ALL named characters, even minor ones.
2. If the translated name is identical to the original name, use that name for both name and translated_name.
3. Extract unique terms, places, organizations, martial arts techniques, or special items into the glossary list.
4. If no characters or terms are found, return empty lists: {"characters": [], "glossary": []}."""


def _clean_json_string(text: str) -> str:
    """Clean markdown codeblocks, trailing commas, and comments from JSON string."""
    cleaned = text.strip()

    # Match JSON inside code fence or outermost braces
    json_match = re.search(r'```(?:json)?\s*([{\[].*?[}\]])\s*```', cleaned, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        start_idx = min((cleaned.find('{'), cleaned.find('[')))
        if start_idx == -1:
            start_idx = max(cleaned.find('{'), cleaned.find('['))
        
        end_idx = max(cleaned.rfind('}'), cleaned.rfind(']'))
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = cleaned[start_idx:end_idx + 1]
        else:
            json_str = cleaned

    # Strip single line comments
    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
    # Strip trailing commas
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    return json_str.strip()


def _normalize_dict_keys(d: Any) -> Any:
    """Recursively convert all dictionary keys to lowercase and stripped string."""
    if isinstance(d, dict):
        return {str(k).lower().strip().replace("-", "_").replace(" ", "_"): _normalize_dict_keys(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_normalize_dict_keys(item) for item in d]
    return d


def _get_first_key_match(d: dict, possible_keys: list[str]) -> Any:
    for k in possible_keys:
        if k in d and d[k] is not None and str(d[k]).strip():
            return d[k]
    return None


def extract_entities_fuzzy(data: Any) -> tuple[list[dict], list[dict]]:
    """Extract character and glossary dict lists from fuzzy JSON data, handling AI typos."""
    characters = []
    glossary = []

    if isinstance(data, dict):
        norm = _normalize_dict_keys(data)

        # Look for nested result containers first
        for wrapper_key in ("data", "result", "output", "response", "extracted", "payload"):
            if wrapper_key in norm and isinstance(norm[wrapper_key], (dict, list)):
                return extract_entities_fuzzy(norm[wrapper_key])

        # Search for character list under fuzzy keys
        char_list = None
        for key in ("characters", "character", "chars", "char_list", "people", "names", "persons", "tokoh", "character_developments", "karakter", "daftar_karakter"):
            if key in norm and isinstance(norm[key], list):
                char_list = norm[key]
                break

        # Search for glossary list under fuzzy keys
        gloss_list = None
        for key in ("glossary", "glosary", "terms", "glossary_terms", "locations", "places", "items", "istilah", "new_names_places", "new_names", "places_and_names", "glosarium"):
            if key in norm and isinstance(norm[key], list):
                gloss_list = norm[key]
                break

        if char_list:
            for item in char_list:
                if isinstance(item, dict):
                    c_name = _get_first_key_match(item, ["name", "char_name", "character_name", "original_name", "original", "src", "character", "tokoh", "nama", "item"])
                    c_trans = _get_first_key_match(item, ["translated_name", "translation", "indonesian_name", "target_name", "translated", "trans", "terjemahan", "nama_terjemahan"]) or c_name
                    c_gender = _get_first_key_match(item, ["gender", "sex", "jenis_kelamin"]) or "unknown"
                    c_speech = _get_first_key_match(item, ["speech_style", "speech", "style", "gaya_bicara"]) or "casual"
                    c_notes = _get_first_key_match(item, ["notes", "note", "description", "desc", "catatan", "role", "background", "context"])
                    if c_name:
                        characters.append({
                            "name": str(c_name).strip(),
                            "translated_name": str(c_trans).strip() if c_trans else str(c_name).strip(),
                            "gender": str(c_gender).lower().strip(),
                            "speech_style": str(c_speech).lower().strip(),
                            "notes": str(c_notes).strip() if c_notes else None,
                        })

        if gloss_list:
            for item in gloss_list:
                if isinstance(item, dict):
                    t_src = _get_first_key_match(item, ["term_source", "source_term", "term", "original_term", "source", "original", "src", "istilah", "nama_istilah", "location", "place", "item"])
                    t_trans = _get_first_key_match(item, ["term_translation", "translation", "target_term", "translated_term", "translated", "target", "trans", "terjemahan", "meaning", "definition"]) or t_src
                    t_notes = _get_first_key_match(item, ["notes", "note", "description", "desc", "catatan", "context"])
                    if t_src and t_trans:
                        glossary.append({
                            "term_source": str(t_src).strip(),
                            "term_translation": str(t_trans).strip(),
                            "notes": str(t_notes).strip() if t_notes else None,
                        })

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                norm_item = _normalize_dict_keys(item)
                if any(k in norm_item for k in ("gender", "speech_style", "character", "tokoh", "role")):
                    c_name = _get_first_key_match(norm_item, ["name", "char_name", "character_name", "original_name", "original", "character"])
                    c_trans = _get_first_key_match(norm_item, ["translated_name", "translation", "target_name"]) or c_name
                    if c_name:
                        characters.append({
                            "name": str(c_name).strip(),
                            "translated_name": str(c_trans).strip() if c_trans else str(c_name).strip(),
                            "gender": str(norm_item.get("gender", "unknown")),
                            "speech_style": str(norm_item.get("speech_style", "casual")),
                            "notes": norm_item.get("notes"),
                        })
                else:
                    t_src = _get_first_key_match(norm_item, ["term_source", "source_term", "term", "original_term", "name"])
                    t_trans = _get_first_key_match(norm_item, ["term_translation", "translation", "target_term", "translated_name"]) or t_src
                    if t_src and t_trans:
                        glossary.append({
                            "term_source": str(t_src).strip(),
                            "term_translation": str(t_trans).strip(),
                            "notes": norm_item.get("notes"),
                        })

    return characters, glossary


def parse_extraction_output(response_text: str) -> tuple[list[dict], list[dict]]:
    """Ultra-resilient multi-strategy JSON & Markdown bullet parser."""
    cleaned = response_text.strip()

    # Strategy 1: Cleaned JSON Parsing
    json_str = _clean_json_string(cleaned)
    try:
        data = json.loads(json_str)
        chars, terms = extract_entities_fuzzy(data)
        if chars or terms:
            return chars, terms
    except Exception:  # noqa: BLE001, S110
        pass

    # Strategy 2: Multi-section Markdown Bullet Point Fallback Parser
    characters = []
    glossary = []
    char_section = False
    gloss_section = False

    for line in cleaned.splitlines():
        line_str = line.strip()
        lower_line = line_str.lower()
        
        # Section Header Detection
        if any(h in lower_line for h in ("character", "tokoh", "nama", "person")):
            char_section = True
            gloss_section = False
            continue
        elif any(h in lower_line for h in ("glossary", "term", "place", "location", "item", "istilah", "glosarium")):
            gloss_section = True
            char_section = False
            continue

        # Bullet point line pattern: - **Name** (Translation): Description
        match = re.match(r'^[-*•]\s*(?:\*\*)?([^*:]+)(?:\*\*)?\s*(?:[:\->=]+|\()?\s*(.*)$', line_str)
        if match:
            item_name = match.group(1).strip()
            item_desc = match.group(2).strip(" :()")
            if not item_name or len(item_name) < 2 or item_name.lower().startswith("key event"):
                continue

            if char_section:
                characters.append({
                    "name": item_name,
                    "translated_name": item_name,
                    "gender": "unknown",
                    "speech_style": "casual",
                    "notes": item_desc or None
                })
            elif gloss_section:
                glossary.append({
                    "term_source": item_name,
                    "term_translation": item_name,
                    "notes": item_desc or None
                })

    return characters, glossary


async def extract_from_chapter(
    *,
    translated_text: str,
    chapter_summary: str | None = None,
    series_id: int,
    model: dict,
    platform: dict,
) -> str:
    """Extract characters and glossary terms from translated text and chapter summary.

    Returns the extract_status: 'done', 'skipped', or 'failed'.
    """
    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    extracted_chars = []
    extracted_terms = []

    # 1. Instant Python Extraction (0.001s) from chapter_summary & translated_text
    if chapter_summary:
        c_sum, t_sum = parse_extraction_output(chapter_summary)
        extracted_chars.extend(c_sum)
        extracted_terms.extend(t_sum)

    c_txt, t_txt = parse_extraction_output(translated_text)
    for c in c_txt:
        if not any(existing.get("name") == c.get("name") for existing in extracted_chars):
            extracted_chars.append(c)
    for t in t_txt:
        if not any(existing.get("term_source") == t.get("term_source") for existing in extracted_terms):
            extracted_terms.append(t)

    # 2. Fast Optional LLM Enrichment Call with 15-second Timeout
    try:
        combined_text = f"TRANSLATED TEXT:\n{translated_text[:4000]}"
        if chapter_summary:
            combined_text += f"\n\nCHAPTER SUMMARY:\n{chapter_summary}"

        response_text = await asyncio.wait_for(
            adapter.call(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=f"Extract all characters and glossary terms from this novel chapter text:\n\n{combined_text}",
                model_name=model["name"],
                base_url=base_url,
                api_key=api_key,
            ),
            timeout=15.0,
        )

        llm_chars, llm_terms = parse_extraction_output(response_text)
        for c in llm_chars:
            if not any(existing.get("name") == c.get("name") for existing in extracted_chars):
                extracted_chars.append(c)
        for t in llm_terms:
            if not any(existing.get("term_source") == t.get("term_source") for existing in extracted_terms):
                extracted_terms.append(t)
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "LLM extraction call skipped or timed out for series %d: %s. Using Python instant extraction results (%d chars, %d terms).",
            series_id, exc, len(extracted_chars), len(extracted_terms)
        )

    char_count = 0
    term_count = 0

    try:
        # Upsert characters
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

        # Upsert glossary terms
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
            "Extraction completed for series %d: Extracted %d characters and %d glossary terms.",
            series_id, char_count, term_count
        )
        return "done"

    except Exception as exc:  # noqa: BLE001
        logger.warning("Extraction DB upsert failed for series %d: %s", series_id, exc)
        return "failed"

