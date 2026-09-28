"""Common interface for paid-media platform adapters.

Centralizing the adapter interface here means the outbound actuation
boundary can treat every ad platform uniformly and each concrete adapter
only needs to implement its platform-specific HTTP call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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
    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply an approved spend/targeting/bid action and return the platform response."""

    async def aclose(self) -> None:
        await self._client.aclose()


class AdsReportingAdapter(ABC):
    """Narrow read-only reporting interface for paid-media platforms."""

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