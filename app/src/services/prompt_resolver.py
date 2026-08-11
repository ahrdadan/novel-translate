"""System prompt resolution service — resolve inline, series, settings, or default system prompts."""

from fastapi import HTTPException

from src.repositories import series_repo, settings_repo, system_prompt_repo


async def resolve_or_create_system_prompt(ref: int | str | dict) -> dict:
    """Resolve a system prompt reference to a system prompt dict.

    Accepts:
      - Direct Integer / String ID: 2 or "2" or {"system_prompt_id": 2} or {"id": 2}
      - Existing Prompt Name: "formal" or {"name": "formal"}
      - Create / Update Prompt: {"name": "wuxia_tone", "promptText": "..."}
      - Custom Inline Text: {"prompt_text": "..."} or "You are a literary translator..."
    """
    if isinstance(ref, (int, str)) and str(ref).isdigit():
        prompt = await system_prompt_repo.get_prompt_by_id(int(ref))
        if not prompt:
            raise HTTPException(404, f"System prompt ID {ref} not found")
        return prompt

    if isinstance(ref, str):
        # Check by name first
        prompt = await system_prompt_repo.get_prompt_by_name(ref)
        if prompt:
            return prompt
        # Treat long string as inline prompt text if not a name
        if len(ref) > 30:
            return {"id": 0, "name": "custom-inline", "prompt_text": ref, "is_default": 0}
        raise HTTPException(404, f"System prompt with name '{ref}' not found")

    if not isinstance(ref, dict):
        raise HTTPException(400, "Invalid system prompt reference format")

    prompt_id = ref.get("system_prompt_id") or ref.get("systemPromptId") or ref.get("id")
    if prompt_id and isinstance(prompt_id, int):
        prompt = await system_prompt_repo.get_prompt_by_id(prompt_id)
        if not prompt:
            raise HTTPException(404, f"System prompt ID {prompt_id} not found")
        return prompt

    name = ref.get("name")
    prompt_text = ref.get("prompt_text") or ref.get("promptText")

    if name and not prompt_text:
        prompt = await system_prompt_repo.get_prompt_by_name(name)
        if not prompt:
            raise HTTPException(404, f"System prompt with name '{name}' not found")
        return prompt

    if not prompt_text:
        raise HTTPException(
            400, "System prompt reference must specify ID, Name, or promptText"
        )

    if name:
        existing = await system_prompt_repo.get_prompt_by_name(name)
        if existing:
            updated = await system_prompt_repo.update_prompt(
                existing["id"], {"prompt_text": prompt_text}
            )
            return updated or existing
        return await system_prompt_repo.create_prompt(name=name, prompt_text=prompt_text)

    return {"id": 0, "name": "custom-inline", "prompt_text": prompt_text, "is_default": 0}



async def resolve_system_prompt_for_series(
    request_prompt_ref: dict | None,
    series_id: int | None = None,
) -> dict:
    """Full resolution hierarchy for system prompts:

    1. Request body system_prompt ref -> resolve_or_create_system_prompt
    2. Series override (series.system_prompt_id)
    3. Settings default (settings.default_system_prompt_id)
    4. Default DB prompt (where is_default = 1)
    """
    # 1. Request body
    if request_prompt_ref:
        return await resolve_or_create_system_prompt(request_prompt_ref)

    # 2. Series override
    if series_id:
        series = await series_repo.get_series_by_id(series_id)
        if series and series.get("system_prompt_id"):
            prompt = await system_prompt_repo.get_prompt_by_id(series["system_prompt_id"])
            if prompt:
                return prompt

    # 3. Settings default
    settings = await settings_repo.get_settings()
    default_id = settings.get("default_system_prompt_id")
    if default_id:
        prompt = await system_prompt_repo.get_prompt_by_id(default_id)
        if prompt:
            return prompt

    # 4. Fallback to default DB prompt
    default_prompt = await system_prompt_repo.get_default_prompt()
    if default_prompt:
        return default_prompt

    raise HTTPException(500, "No default system prompt found in database")
