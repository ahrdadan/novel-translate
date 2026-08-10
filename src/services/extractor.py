"""Extractor service — extract characters and glossary terms from translated text via LLM."""

import json
import logging

from src.repositories import character_repo, glossary_repo
from src.services.llm_adapters import get_adapter

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an assistant that extracts characters and glossary terms from translated novel text.

Respond with a JSON object exactly in this format (no explanation, just JSON):
{
  "characters": [
    {"name": "Original Name", "translated_name": "Translated Name", "gender": "male/female/unknown", "notes": "brief description"}
  ],
  "glossary": [
    {"term_source": "Original Term", "term_translation": "Translation", "notes": "context"}
  ]
}

Rules:
- Extract ALL character names that appear in the text.
- Extract important terms, titles, locations, organizations, techniques, etc.
- For characters, include gender if determinable from context.
- Keep the JSON valid and parseable.
- If no characters or terms found, return empty arrays."""


async def extract_from_chapter(
    *,
    translated_text: str,
    series_id: int,
    model: dict,
    platform: dict,
) -> str:
    """Extract characters and glossary terms from translated text.

    Returns the extract_status: 'done', 'skipped', or 'failed'.
    """
    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    try:
        response_text = await adapter.call(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=f"Extract characters and glossary terms from this translated chapter:\n\n{translated_text}",
            model_name=model["name"],
            base_url=base_url,
            api_key=api_key,
        )

        # Parse JSON response
        # Try to find JSON in the response (LLM might wrap it in markdown)
        json_text = response_text.strip()
        if json_text.startswith("```"):
            # Strip markdown code fences
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1]) if len(lines) > 2 else json_text

        data = json.loads(json_text)

        # Upsert characters
        for char in data.get("characters", []):
            if char.get("name"):
                await character_repo.upsert_character(
                    series_id=series_id,
                    name=char["name"],
                    translated_name=char.get("translated_name"),
                    gender=char.get("gender"),
                    notes=char.get("notes"),
                )

        # Upsert glossary terms
        for term in data.get("glossary", []):
            if term.get("term_source") and term.get("term_translation"):
                await glossary_repo.upsert_term(
                    series_id=series_id,
                    term_source=term["term_source"],
                    term_translation=term["term_translation"],
                    notes=term.get("notes"),
                )

        return "done"

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse extraction response: %s", exc)
        return "failed"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Extraction failed: %s", exc)
        return "failed"

