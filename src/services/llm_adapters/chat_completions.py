"""OpenAI-compatible /v1/chat/completions adapter (default fallback)."""

import httpx

from src.services.llm_adapters.base import BaseLLMAdapter


class ChatCompletionsAdapter(BaseLLMAdapter):
    """Adapter for OpenAI-compatible chat completions API."""

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
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
