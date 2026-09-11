"""Reads staged CMS data and applies approved content/schema changes."""

from __future__ import annotations

import httpx

from app.core.exceptions import ConfigurationError


class CmsClient:
    """Thin HTTP boundary around a configured headless CMS."""

    def __init__(
        self, base_url: str | None, api_key: str | None, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = client or httpx.AsyncClient()

    def _require_configured(self) -> str:
        if not self._base_url:
            raise ConfigurationError("CMS_BASE_URL is not configured.")
        return self._base_url

    async def read_staged(self, content_type: str) -> list[dict[str, str]]:
        """Return staged (unpublished) entries of ``content_type``."""

        base_url = self._require_configured()
        response = await self._client.get(
            f"{base_url}/api/{content_type}",
            params={"status": "staged"},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return response.json()

    async def apply_changes(
        self, content_type: str, entry_id: str, diff: dict[str, str]
    ) -> dict[str, str]:
        """Apply an approved content/schema change to a staged entry."""

        base_url = self._require_configured()
        response = await self._client.patch(
            f"{base_url}/api/{content_type}/{entry_id}",
            json=diff,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "entry_id": entry_id}

    async def aclose(self) -> None:
        await self._client.aclose()