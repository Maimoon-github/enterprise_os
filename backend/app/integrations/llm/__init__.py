"""Provider-neutral AI model boundary."""

from app.integrations.llm.client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_PROVIDER,
    LlmClient,
    LlmResponseError,
    create_default_client,
)

__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_PROVIDER",
    "LlmClient",
    "LlmResponseError",
    "create_default_client",
]
