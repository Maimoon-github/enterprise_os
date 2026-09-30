"""Invokes the configured model/provider without coupling callers to a vendor.

The concrete model provider was unspecified by the source architecture (see
``docs/ASSUMPTIONS.md``). This client speaks the widely-adopted OpenAI-style
chat-completions HTTP shape against a configurable ``base_url``, which lets
it target OpenAI, Azure OpenAI, or any self-hosted OpenAI-compatible gateway
purely through configuration, with zero vendor-specific code in callers.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.exceptions import ConfigurationError
from app.core.settings import LlmSettings

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)

DEFAULT_OLLAMA_MODEL: str = "qwen2.5-coder:7b"
DEFAULT_OLLAMA_CODER_MODEL: str = "qwen2.5-coder:7b"
DEFAULT_OLLAMA_INTELLIGENCE_MODEL: str = "qwen2.5:7b"
DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
DEFAULT_OLLAMA_PROVIDER: str = "ollama"


class LlmResponseError(RuntimeError):
    """Raised when a model response cannot be converted to the requested schema."""


class LlmClient:
    """Provider-neutral chat-completion boundary with local-model priority."""

    DEFAULT_MODEL: str = DEFAULT_OLLAMA_MODEL
    DEFAULT_CODER_MODEL: str = DEFAULT_OLLAMA_CODER_MODEL
    DEFAULT_INTELLIGENCE_MODEL: str = DEFAULT_OLLAMA_INTELLIGENCE_MODEL
    DEFAULT_BASE_URL: str = DEFAULT_OLLAMA_BASE_URL
    DEFAULT_PROVIDER: str = DEFAULT_OLLAMA_PROVIDER

    def __init__(
        self,
        settings: LlmSettings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        agent_identity: str | None = None,
        model_identity: str | None = None,
        default_temperature: float | None = None,
        default_max_output_tokens: int | None = None,
    ) -> None:
        self._settings = settings or LlmSettings(
            provider=self.DEFAULT_PROVIDER,
            base_url=self.DEFAULT_BASE_URL,
            model_name=self.DEFAULT_MODEL,
        )
        self._client = client or httpx.AsyncClient(timeout=self._settings.request_timeout_seconds)
        self._agent_identity = agent_identity
        if model_identity:
            self._model_identity = model_identity
        elif agent_identity == "INTELLIGENCE_ENGINE" and self._settings.intelligence_model_name:
            self._model_identity = self._settings.intelligence_model_name
        elif (
            agent_identity
            and (agent_identity.startswith("W_DEV") or agent_identity.startswith("DEV-"))
            and self._settings.coder_model_name
        ):
            self._model_identity = self._settings.coder_model_name
        elif self._settings.model_name and self._settings.model_name != "unset":
            self._model_identity = self._settings.model_name
        else:
            self._model_identity = self.DEFAULT_MODEL
        self._default_temperature = default_temperature
        self._default_max_output_tokens = default_max_output_tokens
        self._last_metadata: dict[str, Any] = {}

    @property
    def settings(self) -> LlmSettings:
        return self._settings

    @property
    def agent_identity(self) -> str | None:
        return self._agent_identity

    @property
    def model_identity(self) -> str:
        return self._model_identity

    @property
    def default_temperature(self) -> float | None:
        return self._default_temperature

    @property
    def default_max_output_tokens(self) -> int | None:
        return self._default_max_output_tokens

    @property
    def last_metadata(self) -> dict[str, Any]:
        return dict(self._last_metadata)

    def _require_configured(self) -> None:
        if self._settings.provider == "unset" or not self._settings.base_url:
            raise ConfigurationError(
                "LLM_PROVIDER and LLM_BASE_URL must be configured before invoking the model."
            )
        # Local models (ollama, vllm, lmstudio, localhost) do not strictly require API keys;
        # Cloud providers must supply credentials to fail closed on missing configuration.
        if not self._settings.is_local and not self._settings.api_key:
            raise ConfigurationError(
                "LLM_API_KEY must be configured before invoking cloud model providers."
            )

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        if self._settings.is_local:
            return 0.0
        input_cost = (prompt_tokens / 1_000_000.0) * self._settings.cost_per_million_input_tokens
        output_cost = (
            (completion_tokens / 1_000_000.0) * self._settings.cost_per_million_output_tokens
        )
        return round(input_cost + output_cost, 6)

    async def complete_with_metadata(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return (completion_text, metadata) with observable model identity and token usage."""

        self._require_configured()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers: dict[str, str] = {}
        api_key = self._settings.api_key or ("local" if self._settings.is_local else "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        effective_temp = temperature if temperature is not None else self._default_temperature
        effective_max_tokens = (
            max_output_tokens if max_output_tokens is not None else self._default_max_output_tokens
        )
        effective_model = self._model_identity
        request_body: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
        }
        if effective_temp is not None:
            request_body["temperature"] = effective_temp
        if effective_max_tokens is not None:
            request_body["max_tokens"] = effective_max_tokens

        try:
            response = await self._client.post(
                f"{self._settings.base_url}/chat/completions",
                json=request_body,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LlmResponseError(
                f"LLM provider request timed out after {self._settings.request_timeout_seconds}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LlmResponseError(
                f"LLM provider returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LlmResponseError(f"LLM provider network request failed: {exc}") from exc

        body = response.json()
        choices = body.get("choices")
        if not choices or not isinstance(choices, list) or "message" not in choices[0]:
            raise LlmResponseError("Malformed completion response from LLM provider")

        content = choices[0]["message"].get("content", "")
        actual_model = body.get("model", effective_model)
        usage = body.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost = self._calculate_cost(prompt_tokens, completion_tokens)

        metadata = {
            "agent_identity": self._agent_identity,
            "model_identity": self._model_identity,
            "provider": self._settings.provider,
            "configured_model": effective_model,
            "actual_model": actual_model,
            "is_local": self._settings.is_local,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": cost,
            "temperature": effective_temp,
            "max_output_tokens": effective_max_tokens,
        }
        self._last_metadata = metadata
        return content, metadata

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Return the model's completion for ``prompt``."""
        content, _ = await self.complete_with_metadata(
            prompt,
            system=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return content

    async def generate(
        self,
        prompt: str | None = None,
        *,
        system: str | None = None,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Universal generate method supporting prompt/system and user_prompt/system_prompt."""
        effective_prompt = prompt or user_prompt or ""
        effective_system = system or system_prompt
        temperature = kwargs.get("temperature")
        max_output_tokens = kwargs.get("max_output_tokens")
        return await self.complete(
            effective_prompt,
            system=effective_system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
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

        content = await self.complete(
            user_prompt,
            system=structured_system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        payload = self._parse_json_object(content)

        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LlmResponseError(
                f"LLM response did not satisfy {response_model.__name__}"
            ) from exc

    async def generate_structured_with_metadata(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> tuple[ResponseModelT, dict[str, Any]]:
        """Generate structured output and return (response_model, metadata)."""
        result = await self.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return result, self.last_metadata

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


def create_default_client(
    agent_identity: str | None = None,
    *,
    model_identity: str | None = None,
    base_settings: LlmSettings | None = None,
    client: httpx.AsyncClient | None = None,
    default_temperature: float | None = None,
    default_max_output_tokens: int | None = None,
) -> LlmClient:
    """Create an LlmClient targeting the default local Ollama Qwen 2.5 Coder 7B model.

    This provides a unified, zero-cost, privacy-first local LLM boundary for:
    - Intelligence Engine (IE)
    - 7 Layer-5 Worker Agents (W_DEV, W_STRAT, W_CREAT, W_PROD, W_COMP, W_VOICE, W_LEARN)
    - 38 Layer-6 Specialist Sub-Agents
    """
    settings = base_settings or LlmSettings(
        provider=DEFAULT_OLLAMA_PROVIDER,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        model_name=DEFAULT_OLLAMA_MODEL,
    )
    return LlmClient(
        settings=settings,
        client=client,
        agent_identity=agent_identity,
        model_identity=model_identity or DEFAULT_OLLAMA_MODEL,
        default_temperature=default_temperature,
        default_max_output_tokens=default_max_output_tokens,
    )


def create_intelligence_client(
    agent_identity: str = "INTELLIGENCE_ENGINE",
    *,
    model_identity: str | None = None,
    base_settings: LlmSettings | None = None,
    client: httpx.AsyncClient | None = None,
    default_temperature: float | None = None,
    default_max_output_tokens: int | None = None,
) -> LlmClient:
    """Create an LlmClient specifically for the Intelligence Engine orchestrator using qwen2.5:7b."""
    settings = base_settings or LlmSettings(
        provider=DEFAULT_OLLAMA_PROVIDER,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        model_name=DEFAULT_OLLAMA_INTELLIGENCE_MODEL,
    )
    resolved_model = (
        model_identity
        or (settings.intelligence_model_name if settings.intelligence_model_name else None)
        or DEFAULT_OLLAMA_INTELLIGENCE_MODEL
    )
    return LlmClient(
        settings=settings,
        client=client,
        agent_identity=agent_identity,
        model_identity=resolved_model,
        default_temperature=default_temperature,
        default_max_output_tokens=default_max_output_tokens,
    )


def create_coder_client(
    agent_identity: str = "W_DEV",
    *,
    model_identity: str | None = None,
    base_settings: LlmSettings | None = None,
    client: httpx.AsyncClient | None = None,
    default_temperature: float | None = None,
    default_max_output_tokens: int | None = None,
) -> LlmClient:
    """Create an LlmClient specifically for Development Worker and coding specialists using qwen2.5-coder:7b."""
    settings = base_settings or LlmSettings(
        provider=DEFAULT_OLLAMA_PROVIDER,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        model_name=DEFAULT_OLLAMA_CODER_MODEL,
    )
    resolved_model = (
        model_identity
        or (settings.coder_model_name if settings.coder_model_name else None)
        or DEFAULT_OLLAMA_CODER_MODEL
    )
    return LlmClient(
        settings=settings,
        client=client,
        agent_identity=agent_identity,
        model_identity=resolved_model,
        default_temperature=default_temperature,
        default_max_output_tokens=default_max_output_tokens,
    )

