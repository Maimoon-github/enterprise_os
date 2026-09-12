"""Invokes the configured model/provider without coupling callers to a vendor.

The concrete model provider was unspecified by the source architecture (see
``docs/ASSUMPTIONS.md``). This client speaks the widely-adopted OpenAI-style
chat-completions HTTP shape against a configurable ``base_url``, which lets
it target OpenAI, Azure OpenAI, or any self-hosted OpenAI-compatible gateway
purely through configuration, with zero vendor-specific code in callers.
"""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.exceptions import ConfigurationError
from app.core.settings import LlmSettings


ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class LlmResponseError(RuntimeError):
    """Raised when a model response cannot be converted to the requested schema."""


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

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
    ) -> ResponseModelT:
        """Generate and validate a JSON response against ``response_model``.

        Structured generation is implemented above the provider transport
        instead of relying on a vendor-specific response-format API. The
        Intelligence Engine therefore depends only on this typed contract.
        """

        schema = json.dumps(
            response_model.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        structured_system = (
            f"{system_prompt.rstrip()}\n\n"
            "Return exactly one JSON object matching the supplied JSON Schema. "
            "Do not wrap it in markdown and do not add explanatory text.\n"
            f"JSON Schema:\n{schema}"
        )

        content = await self.complete(user_prompt, system=structured_system)
        payload = self._parse_json_object(content)

        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LlmResponseError(
                f"LLM response did not satisfy {response_model.__name__}"
            ) from exc

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, object]:
        """Parse one JSON object while tolerating an accidental code fence."""

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LlmResponseError("LLM response was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise LlmResponseError("LLM structured response must be a JSON object")
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()
