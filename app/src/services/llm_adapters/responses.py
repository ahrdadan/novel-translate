import asyncio
import logging

import httpx

from src.services.llm_adapters.base import BaseLLMAdapter

logger = logging.getLogger(__name__)


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
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        base_clean = base_url.rstrip("/")
        if base_clean.endswith(("/v1/responses", "/responses")):
            url = base_clean

        elif base_clean.endswith("/v1"):
            url = f"{base_clean}/responses"
        else:
            url = f"{base_clean}/v1/responses"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "instructions": system_prompt,
            "input": user_prompt,
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
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
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt < max_retries and (status_code in (429, 500, 502, 503, 504) or isinstance(exc, httpx.RequestError)):
                    sleep_time = attempt * 2
                    logger.warning(
                        "Responses API call attempt %d/%d failed (%s). Retrying in %ds...",
                        attempt, max_retries, exc, sleep_time
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    raise

    async def call_stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        base_url: str,
        api_key: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        # NOTE: responses API (e.g. Vertex predict) streaming format varies heavily.
        # Fallback to standard call and yield the whole response as a single chunk.
        res = await self.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        yield res
