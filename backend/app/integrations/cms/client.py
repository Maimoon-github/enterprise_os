"""Reads staged CMS data and applies approved content/schema changes."""

from __future__ import annotations

import httpx

from app.core.exceptions import ConfigurationError


from typing import Any
import httpx

from app.core.exceptions import ConfigurationError


class CmsClient:
    """Thin HTTP boundary around a configured headless CMS with staged-content fallback."""

    def __init__(
        self, base_url: str | None, api_key: str | None, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = client or httpx.AsyncClient()
        self._staged_store: dict[str, dict[str, dict[str, Any]]] = {}

    def _require_configured(self) -> str:
        if not self._base_url:
            raise ConfigurationError("CMS_BASE_URL is not configured.")
        return self._base_url

    async def stage_entry(
        self, content_type: str, entry_id: str, data: dict[str, Any], tenant_id: str | None = None
    ) -> None:
        """Register a staged content entry in the CMS."""

        bucket = self._staged_store.setdefault(content_type, {})
        entry = dict(data)
        entry["id"] = entry_id
        entry["status"] = "staged"
        if tenant_id:
            entry["tenant_id"] = tenant_id
        bucket[entry_id] = entry

    async def read_staged(self, content_type: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Return staged (unpublished) entries of ``content_type``."""

        if not self._base_url:
            entries = list(self._staged_store.get(content_type, {}).values())
            if tenant_id:
                entries = [e for e in entries if e.get("tenant_id") in (None, tenant_id)]
            return entries

        base_url = self._require_configured()
        params: dict[str, str] = {"status": "staged"}
        if tenant_id:
            params["tenant_id"] = tenant_id
        response = await self._client.get(
            f"{base_url}/api/{content_type}",
            params=params,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return response.json()

    async def apply_changes(
        self, content_type: str, entry_id: str, diff: dict[str, Any], tenant_id: str | None = None
    ) -> dict[str, str]:
        """Apply an approved content/schema change to a staged entry."""

        if not self._base_url:
            bucket = self._staged_store.setdefault(content_type, {})
            current = bucket.get(entry_id, {"id": entry_id, "status": "staged"})
            if tenant_id:
                current["tenant_id"] = tenant_id
            current.update(diff)
            bucket[entry_id] = current
            return {"status_code": "200", "entry_id": entry_id, "status": "updated"}

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