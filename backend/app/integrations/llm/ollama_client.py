import json
import logging
from typing import Any

import httpx
from app.core.config import settings

logger = logging.getLogger("integrations.ollama")


class OllamaInvariantError(ValueError):
    """Raised when Ollama tool calling and structured output formats are combined in violation of Issue #8095."""


class OllamaClient:
    """Ollama API Client strictly separating tool-calling turns from structured outputs (Issue #8095)."""

    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL):
        self.base_url = base_url

    def validate_request_invariants(
        self,
        tools: list[dict[str, Any]] | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate Issue #8095 invariant and enforce deterministic structured output parameters."""
        if tools and format is not None:
            raise OllamaInvariantError(
                "Ollama Issue #8095 Invariant Violation: Combining 'tools' (function calling) "
                "and 'format' (structured JSON schema) in the same request causes empty tool_calls regressions. "
                "Separate tool-calling turns from structured schema compilation turns."
            )

        resolved_options = dict(options or {})
        if format is not None:
            # Enforce temperature=0 and num_ctx=32768 on structured outputs
            resolved_options.setdefault("temperature", 0.0)
            resolved_options.setdefault("num_ctx", 32768)

        return resolved_options

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        resolved_options = self.validate_request_invariants(tools=None, format=format, options=options)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120.0) as client:
            payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            if format is not None:
                payload["format"] = format
            if resolved_options:
                payload["options"] = resolved_options

            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "")

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Execute chat turn strictly separating tool calling from structured output schemas."""
        resolved_options = self.validate_request_invariants(tools=tools, format=format, options=options)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if format is not None:
            payload["format"] = format
        if resolved_options:
            payload["options"] = resolved_options

        async with httpx.AsyncClient(base_url=self.base_url, timeout=120.0) as client:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def structured_output(
        self,
        model: str,
        messages: list[dict[str, Any]],
        schema: Any,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Helper to invoke Ollama with schema.model_json_schema(), temperature=0, num_ctx=32768."""
        json_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema
        res = await self.chat(
            model=model,
            messages=messages,
            tools=None,
            format=json_schema,
            options=options,
        )
        content = res.get("message", {}).get("content", "{}")
        return json.loads(content)


ollama_client = OllamaClient()
