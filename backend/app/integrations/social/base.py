"""Common interface for organic social-channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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
    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Publish an approved piece of content and return the platform response."""

    async def aclose(self) -> None:
        await self._client.aclose()


SocialMediaAdapter = SocialAdapter


class SocialReportingAdapter(ABC):
    """Narrow read-only reporting interface for organic social channels."""

    channel: str

    def __init__(
        self,
        access_token: str | None,
        *,
        client: httpx.AsyncClient | None = None,
        api_version: str | None = None,
        account_id: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._client = client or httpx.AsyncClient()
        self._api_version = api_version
        self._account_id = account_id

    @property
    def api_version(self) -> str | None:
        return self._api_version

    @abstractmethod
    async def fetch_report_page(
        self,
        *,
        account_id: str,
        report_spec: dict[str, Any],
        cursor: str | None = None,
        limit: int = 100,
        cost_budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Fetch a single bounded report page from the platform."""

    async def aclose(self) -> None:
        await self._client.aclose()