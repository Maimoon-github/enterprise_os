"""Common interface for organic social-channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class SocialAdapter(ABC):
    """A single organic social channel's publishing/engagement boundary."""

    channel: str

    def __init__(
        self, access_token: str | None, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._access_token = access_token
        self._client = client or httpx.AsyncClient()

    @abstractmethod
    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        """Publish an approved piece of content and return the platform response."""

    async def aclose(self) -> None:
        await self._client.aclose()