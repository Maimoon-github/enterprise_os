"""Invokes the configured model/provider without coupling callers to a vendor.

The concrete model provider was unspecified by the source architecture (see
``docs/ASSUMPTIONS.md``). This client speaks the widely-adopted OpenAI-style
chat-completions HTTP shape against a configurable ``base_url``, which lets
it target OpenAI, Azure OpenAI, or any self-hosted OpenAI-compatible gateway
purely through configuration, with zero vendor-specific code in callers.
"""

from __future__ import annotations

import httpx

from app.core.exceptions import ConfigurationError
from app.core.settings import LlmSettings


class LlmClient:
    """Provider-neutral chat-completion boundary for the configured model."""

    def __init__(self, settings: LlmSettings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=settings.request_timeout_seconds)

    def _require_configured(self) -> None:
        if self._settings.provider == "unset" or not self._settings.base_url:
            raise ConfigurationError(
                "LLM_PROVIDER and LLM_BASE_URL must be configured before invoking the model."
            )

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's completion for ``prompt``."""

        self._require_configured()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.post(
            f"{self._settings.base_url}/chat/completions",
            json={"model": self._settings.model_name, "messages": messages},
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        await self._client.aclose()