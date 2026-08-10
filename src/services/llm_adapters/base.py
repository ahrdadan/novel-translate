"""Abstract base class for LLM API adapters."""

from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """Interface that each API-type adapter must implement.

    Every adapter normalises the provider-specific request/response format
    and returns plain text output to the caller.
    """

    @abstractmethod
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
        """Send a prompt to the LLM and return the text response."""
        ...
