import asyncio
import logging

import httpx

from src.services.llm_adapters.base import BaseLLMAdapter

logger = logging.getLogger(__name__)


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
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: int = 600,
    ) -> str:
        base_clean = base_url.rstrip("/")
        if base_clean.endswith(("/v1/messages", "/messages")):
            url = base_clean

        elif base_clean.endswith("/v1"):
            url = f"{base_clean}/messages"
        else:
            url = f"{base_clean}/v1/messages"
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
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(float(timeout), connect=10.0)) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                # Anthropic returns content as a list of blocks
                content_blocks = data.get("content", [])
                texts = [block["text"] for block in content_blocks if block.get("type") == "text"]
                if texts:
                    return "\n".join(texts)
                raise ValueError(f"Could not extract text from messages API output: {data}")
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt < max_retries and (status_code in (429, 500, 502, 503, 504) or isinstance(exc, httpx.RequestError)):
                    sleep_time = attempt * 2
                    logger.warning(
                        "Messages API call attempt %d/%d failed (%s). Retrying in %ds...",
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
        timeout: int = 600,
    ):
        import json
        base_clean = base_url.rstrip("/")
        if base_clean.endswith(("/v1/messages", "/messages")):
            url = base_clean
        elif base_clean.endswith("/v1"):
            url = f"{base_clean}/messages"
        else:
            url = f"{base_clean}/v1/messages"
            
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
            "max_tokens": max_tokens or 4096,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                async with (
                    httpx.AsyncClient(timeout=httpx.Timeout(float(timeout), connect=10.0)) as client,
                    client.stream("POST", url, json=payload, headers=headers) as resp
                ):
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith("event:"):
                            continue
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "content_block_delta":
                                    delta = data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield delta.get("text", "")
                            except Exception:  # noqa: BLE001, S110
                                pass
                    return
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt < max_retries and (status_code in (429, 500, 502, 503, 504) or isinstance(exc, httpx.RequestError)):
                    sleep_time = attempt * 2
                    logger.warning(
                        "Messages API stream attempt %d/%d failed (%s). Retrying in %ds...",
                        attempt, max_retries, exc, sleep_time
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    raise
