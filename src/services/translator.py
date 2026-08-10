"""Translation service — chapter translation via resolved LLM adapter.

System prompt is resolved dynamically via DB or request/series overrides.
Critical previous context instruction is always appended automatically.
"""

from typing import Any

from src.repositories import chapter_repo, glossary_repo
from src.services import prompt_resolver
from src.services.llm_adapters import get_adapter

DEFAULT_SYSTEM_PROMPT = """You are a professional literary translator specializing in novel translation, writing with the sensibility of a native Indonesian author.

Rules:
- Translate naturally and idiomatically into fluent, contemporary Indonesian — avoid stiff, literal, or overly wordy "translated" phrasing.
- Preserve the author's voice: writing style, tone, register, and atmosphere.
- Do NOT summarize, shorten, paraphrase away detail, add explanations, or remove information.
- Keep each character's distinct voice and speech register consistent through diction and sentence structure, NOT through pronoun switching.
- Use "aku" as the default first-person pronoun, including its natural contracted forms ("kudengar", "kutahu"), and "kau"/"kamu" as the default second-person pronoun. Use "saya"/"Anda" only in clearly formal contexts. NEVER use slang/informal pronouns such as "gue", "gw", "lu", "elu", "situ".
- Keep dialogue formatting, punctuation style, and paragraph breaks exactly as in the original.
- Keep proper nouns entirely UNCHANGED (names, locations, organizations, factions).
- Do NOT translate honorifics, titles, cultivation stages, or martial arts/magic techniques. Keep them in English (e.g., "Young Master", "Senior Brother", "Duke", "Fireball") or in Romanized/Latin format if translating directly from Japanese/Korean/Chinese.
- Localize interjections, curses, and onomatopoeia naturally, matching the original's intensity.
- Do not censor explicit, violent, or sensitive content.
- Make dialogue and internal monologue sound like something an Indonesian speaker would actually say/think.
- Preserve any HTML tags or Markdown formatting (e.g. *italics*, **bold**) exactly in the output, correctly positioned.
- Output ONLY the translated text corresponding to "CURRENT TEXT TO TRANSLATE", formatted as valid markdown — no explanations, notes, or commentary."""

CRITICAL_INSTRUCTION = """

CRITICAL INSTRUCTION:
You may receive text separated into "PREVIOUS CONTEXT" and "CURRENT TEXT TO TRANSLATE". You must ONLY translate the text under "CURRENT TEXT TO TRANSLATE". Use the "PREVIOUS CONTEXT" strictly as background information to maintain consistent tone, names, and pronouns. DO NOT translate or output the previous context."""


async def translate_chapter(
    *,
    source_text: str,
    series_id: int,
    chapter_number: float,
    model: dict,
    platform: dict,
    system_prompt_ref: dict | None = None,
    progress_callback: Any | None = None,
    return_details: bool = False,
) -> str | dict:
    """Translate a chapter using resolved model, platform, and system prompt.

    Supports chunking long text into paragraph batches and reporting real-time progress callbacks.
    """
    # 1. Resolve base system prompt
    prompt_obj = await prompt_resolver.resolve_system_prompt_for_series(
        system_prompt_ref, series_id
    )
    base_prompt_text = prompt_obj.get("prompt_text") or DEFAULT_SYSTEM_PROMPT

    # 2. Append CRITICAL INSTRUCTION automatically as required
    system_prompt = base_prompt_text + CRITICAL_INSTRUCTION

    # 3. Build glossary prompt from DB
    glossary_terms = await glossary_repo.get_terms_by_series(series_id)
    glossary_prompt = _build_glossary_prompt(glossary_terms)
    if glossary_prompt:
        system_prompt += glossary_prompt

    # 4. Build context prompt from previous chapter summary
    prev_summary = await chapter_repo.get_previous_chapter_summary(series_id, chapter_number)
    context_prompt = _build_context_prompt(prev_summary)

    # 5. Build user prompt with previous context and full chapter text (No Chunking)
    user_prompt = ""
    if context_prompt:
        user_prompt += context_prompt
    user_prompt += f"\n\nCURRENT TEXT TO TRANSLATE:\n{source_text}"

    paragraphs = [p.strip() for p in source_text.split("\n\n") if p.strip()]
    total_paragraphs = len(paragraphs) if paragraphs else 1

    if progress_callback:
        try:
            await progress_callback({
                "substage": "translating_full_chapter",
                "total_paragraphs": total_paragraphs,
                "message": f"Translating 1 full chapter ({total_paragraphs} paragraphs, {len(source_text)} chars)...",
            })
        except Exception:  # noqa: BLE001, S110
            pass

    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    translated_text = await adapter.call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=model["name"],
        base_url=base_url,
        api_key=api_key,
    )

    if progress_callback:
        try:
            await progress_callback({
                "substage": "translated_full_chapter_complete",
                "total_paragraphs": total_paragraphs,
                "message": f"Full chapter translation completed ({len(translated_text)} chars generated)",
            })
        except Exception:  # noqa: BLE001, S110
            pass

    clean_text = translated_text.strip()

    if return_details:
        return {
            "translated_text": clean_text,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": translated_text,
        }

    return clean_text


def _build_glossary_prompt(terms: list[dict]) -> str:
    if not terms:
        return ""
    prompt = "\n\nGLOSSARY (Strictly enforce these terms/names):\n"
    for t in terms:
        note = f" ({t['notes']})" if t.get("notes") else ""
        prompt += f"- {t['term_source']} -> {t['term_translation']}{note}\n"
    return prompt


def _build_context_prompt(previous_summary: str | None) -> str:
    if not previous_summary:
        return ""
    return f"\n\nPREVIOUS CONTEXT (For background info only, DO NOT TRANSLATE THIS):\n{previous_summary}\n"
