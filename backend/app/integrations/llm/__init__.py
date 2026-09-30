"""Provider-neutral AI model boundary."""

from app.integrations.llm.client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_CODER_MODEL,
    DEFAULT_OLLAMA_INTELLIGENCE_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_PROVIDER,
    LlmClient,
    LlmResponseError,
    create_coder_client,
    create_default_client,
    create_intelligence_client,
)

__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_CODER_MODEL",
    "DEFAULT_OLLAMA_INTELLIGENCE_MODEL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_PROVIDER",
    "LlmClient",
    "LlmResponseError",
    "create_coder_client",
    "create_default_client",
    "create_intelligence_client",
]
