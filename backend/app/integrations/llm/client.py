"""Invokes the configured model/provider without coupling agents to a vendor."""
from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def complete(self, prompt: str, **options) -> str: ...


class ProviderNeutralLlmClient:
    def __init__(self, provider_callable) -> None:
        self._provider_callable = provider_callable

    def complete(self, prompt: str, **options) -> str:
        return self._provider_callable(prompt, **options)
