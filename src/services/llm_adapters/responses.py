"""OpenAI /v1/responses adapter."""

import httpx

from src.services.llm_adapters.base import BaseLLMAdapter


class ResponsesAdapter(BaseLLMAdapter):
    """Adapter for OpenAI Responses API format."""

    async def call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        base_url: str,
        api_key: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        url = f"{base_url.rstrip('/')}/v1/responses"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Extract text from response output items
        output_items = data.get("output", [])
        for item in output_items:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
        # Fallback: try direct output_text field
        if "output_text" in data:
            return data["output_text"]
        raise ValueError(f"Could not extract text from responses API output: {data}")
