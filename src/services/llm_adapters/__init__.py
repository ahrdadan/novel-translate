"""LLM Adapter registry — maps api_type to adapter instance."""

from src.services.llm_adapters.base import BaseLLMAdapter
from src.services.llm_adapters.chat_completions import ChatCompletionsAdapter
from src.services.llm_adapters.messages import MessagesAdapter
from src.services.llm_adapters.responses import ResponsesAdapter

ADAPTERS: dict[str, BaseLLMAdapter] = {
    "chat-completions": ChatCompletionsAdapter(),
    "responses": ResponsesAdapter(),
    "messages": MessagesAdapter(),
}


def get_adapter(api_type: str) -> BaseLLMAdapter:
    """Return the adapter for the given api_type, with chat-completions as fallback."""
    return ADAPTERS.get(api_type, ADAPTERS["chat-completions"])
