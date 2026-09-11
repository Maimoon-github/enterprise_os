"""Common interface for paid-media platform adapters.

Centralizing the adapter interface here means the outbound actuation
boundary can treat every ad platform uniformly and each concrete adapter
only needs to implement its platform-specific HTTP call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class AdsAdapter(ABC):
    """A single paid-media platform's campaign/targeting/bid/telemetry boundary."""

    channel: str

    def __init__(
        self, access_token: str | None, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._access_token = access_token
        self._client = client or httpx.AsyncClient()

    @abstractmethod
    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        """Apply an approved spend/targeting/bid action and return the platform response."""

    async def aclose(self) -> None:
        await self._client.aclose()