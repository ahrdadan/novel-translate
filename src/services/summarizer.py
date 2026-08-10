"""Summarizer service — generates chapter summaries via LLM."""

from src.services.llm_adapters import get_adapter

SUMMARY_SYSTEM_PROMPT = "You are a helpful assistant that generates concise novel plot summaries."


async def summarize_chapter(
    *,
    translated_text: str,
    previous_summary: str | None,
    model: dict,
    platform: dict,
) -> str:
    """Generate a chapter summary using the resolved model.

    If a previous summary exists, asks the LLM to merge old + new into
    a cohesive running summary (max 3 paragraphs).
    """
    prompt = (
        "You are an assistant that summarizes the plot of a novel chapter.\n"
        "Below is the newly translated chapter text. "
        "Please provide a concise summary of the key events, character "
        "developments, and new names/places introduced in this chapter.\n"
    )
    if previous_summary:
        prompt += (
            f"\nFor context, here is the summary of the story up to the previous chapter:\n"
            f"{previous_summary}\n\n"
            "Please combine the previous summary and the new chapter's events "
            "into a single, cohesive running summary (keep it under 3 paragraphs).\n"
        )
    prompt += f"\n\nNEW CHAPTER TEXT:\n{translated_text}"

    adapter = get_adapter(platform.get("api_type", "chat-completions"))
    base_url = model.get("url") or ""
    api_key = platform.get("api_key") or ""

    return await adapter.call(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=model["name"],
        base_url=base_url,
        api_key=api_key,
    )
