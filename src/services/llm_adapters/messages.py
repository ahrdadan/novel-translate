"""Anthropic-style /v1/messages adapter."""

import httpx

from src.services.llm_adapters.base import BaseLLMAdapter


class MessagesAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Messages API format."""

    async def call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        base_url: str,
        api_key: str,
        max_tokens: int = 65536,
        temperature: float = 0.3,
    ) -> str:
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Anthropic returns content as a list of blocks
        content_blocks = data.get("content", [])
        texts = [block["text"] for block in content_blocks if block.get("type") == "text"]
        if texts:
            return "\n".join(texts)
        raise ValueError(f"Could not extract text from messages API output: {data}")
