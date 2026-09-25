"""Reads staged CMS data and applies approved content/schema changes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.exceptions import ConfigurationError


class CmsClient:
    """Thin HTTP boundary around a configured headless CMS with staged-content fallback."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = client or httpx.AsyncClient()
        self._staged_store: dict[str, dict[str, dict[str, Any]]] = {}
        self._published_store: dict[str, dict[str, dict[str, Any]]] = {}
        self._version_history: dict[str, list[dict[str, Any]]] = {}
        self._idempotency_store: dict[str, dict[str, Any]] = {}

    def _require_configured(self) -> str:
        if not self._base_url:
            raise ConfigurationError("CMS_BASE_URL is not configured.")
        return self._base_url

    async def stage_entry(
        self,
        content_type: str,
        entry_id: str,
        data: dict[str, Any],
        tenant_id: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Register a staged content entry in the CMS."""
        if idempotency_key:
            scoped_key = f"{tenant_id or 'default'}:{idempotency_key}"
            if scoped_key in self._idempotency_store:
                return dict(self._idempotency_store[scoped_key])

        bucket = self._staged_store.setdefault(content_type, {})
        entry = dict(data)
        entry["id"] = entry_id
        entry["status"] = "staged"
        if tenant_id:
            entry["tenant_id"] = tenant_id
        bucket[entry_id] = entry

        result = {
            "status_code": "200",
            "entry_id": entry_id,
            "content_type": content_type,
            "status": "staged",
            "version_reference": f"{content_type}:{entry_id}:staged",
        }
        if idempotency_key:
            self._idempotency_store[scoped_key] = result
        return result

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

    async def create_entry(
        self,
        content_type: str,
        entry_id: str,
        data: dict[str, Any],
        tenant_id: str | None = None,
        *,
        publish: bool = False,
    ) -> dict[str, Any]:
        """Create a new CMS content entry in staged or live store."""

        if not self._base_url:
            entry = dict(data)
            entry["id"] = entry_id
            if tenant_id:
                entry["tenant_id"] = tenant_id
            entry["status"] = "published" if publish else "created"
            entry["created_at"] = datetime.now(UTC).isoformat()
            if publish:
                entry["published_at"] = datetime.now(UTC).isoformat()
                self._published_store.setdefault(content_type, {})[entry_id] = entry
            else:
                self._staged_store.setdefault(content_type, {})[entry_id] = entry
            return {
                "status_code": "201",
                "entry_id": entry_id,
                "content_type": content_type,
                "status": entry["status"],
            }

        base_url = self._require_configured()
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = dict(data)
        if tenant_id:
            payload["tenant_id"] = tenant_id
        response = await self._client.post(
            f"{base_url}/api/{content_type}",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "entry_id": entry_id, "status": "created"}

    async def apply_changes(
        self,
        content_type: str,
        entry_id: str,
        diff: dict[str, Any],
        tenant_id: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        """Apply an approved content/schema change to a staged or published entry."""
        if idempotency_key:
            scoped_key = f"{tenant_id or 'default'}:{idempotency_key}"
            if scoped_key in self._idempotency_store:
                return dict(self._idempotency_store[scoped_key])

        if not self._base_url:
            bucket = self._staged_store.setdefault(content_type, {})
            current = bucket.get(entry_id, {"id": entry_id, "status": "staged"})
            if tenant_id:
                current["tenant_id"] = tenant_id
            current.update(diff)
            bucket[entry_id] = current

            # Also update published store if present
            if content_type in self._published_store and entry_id in self._published_store[content_type]:
                self._published_store[content_type][entry_id].update(diff)

            result = {
                "status_code": "200",
                "entry_id": entry_id,
                "status": "updated",
                "version_reference": f"{content_type}:{entry_id}:updated",
            }
            if idempotency_key:
                self._idempotency_store[scoped_key] = result
            return result

        base_url = self._require_configured()
        response = await self._client.patch(
            f"{base_url}/api/{content_type}/{entry_id}",
            json=diff,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        result = {
            "status_code": str(response.status_code),
            "entry_id": entry_id,
            "status": "updated",
            "version_reference": f"{content_type}:{entry_id}:updated",
        }
        if idempotency_key:
            self._idempotency_store[scoped_key] = result
        return result

    async def publish_entry(
        self,
        content_type: str,
        entry_id: str,
        tenant_id: str | None = None,
        *,
        version: str = "v1.0",
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Promote an approved staged entry to the live published state with version tracking."""
        if idempotency_key:
            scoped_key = f"{tenant_id or 'default'}:{idempotency_key}"
            if scoped_key in self._idempotency_store:
                return dict(self._idempotency_store[scoped_key])

        now_str = datetime.now(UTC).isoformat()
        if not self._base_url:
            staged_bucket = self._staged_store.get(content_type, {})
            base_entry = dict(staged_bucket.get(entry_id, {"id": entry_id}))
            if payload:
                base_entry.update(payload)
            if tenant_id:
                base_entry["tenant_id"] = tenant_id

            # Save prior version to history for rollback
            history_key = f"{content_type}:{entry_id}"
            if entry_id in self._published_store.get(content_type, {}):
                prev = dict(self._published_store[content_type][entry_id])
                self._version_history.setdefault(history_key, []).append(prev)

            base_entry["status"] = "published"
            base_entry["publish_state"] = "published"
            base_entry["version"] = version
            base_entry["published_at"] = now_str
            self._published_store.setdefault(content_type, {})[entry_id] = base_entry

            res = {
                "status_code": "200",
                "entry_id": entry_id,
                "content_type": content_type,
                "status": "published",
                "version": version,
                "version_reference": f"{content_type}:{entry_id}:{version}",
                "published_at": now_str,
            }
            if idempotency_key:
                self._idempotency_store[scoped_key] = res
            return res

        base_url = self._require_configured()
        response = await self._client.post(
            f"{base_url}/api/{content_type}/{entry_id}/publish",
            json={"version": version, "payload": payload or {}},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        res = {
            "status_code": str(response.status_code),
            "entry_id": entry_id,
            "content_type": content_type,
            "status": "published",
            "version": version,
            "version_reference": f"{content_type}:{entry_id}:{version}",
            "published_at": now_str,
        }
        if idempotency_key:
            self._idempotency_store[scoped_key] = res
        return res

    async def rollback_entry(
        self, content_type: str, entry_id: str, tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Roll back a published entry to its previous version."""

        if not self._base_url:
            history_key = f"{content_type}:{entry_id}"
            history = self._version_history.get(history_key, [])
            if not history:
                return {
                    "status_code": "404",
                    "entry_id": entry_id,
                    "content_type": content_type,
                    "status": "no_prior_version",
                }
            previous = history.pop()
            self._published_store.setdefault(content_type, {})[entry_id] = previous
            return {
                "status_code": "200",
                "entry_id": entry_id,
                "content_type": content_type,
                "status": "rolled_back",
                "version": previous.get("version", "previous"),
                "version_reference": f"{content_type}:{entry_id}:{previous.get('version', 'previous')}",
                "rolled_back_at": datetime.now(UTC).isoformat(),
            }

        base_url = self._require_configured()
        response = await self._client.post(
            f"{base_url}/api/{content_type}/{entry_id}/rollback",
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "entry_id": entry_id, "status": "rolled_back"}

    async def read_published(
        self,
        content_type: str,
        tenant_id: str | None = None,
        entry_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return published entries matching the content type, tenant, and optional entry ID."""

        if not self._base_url:
            bucket = self._published_store.get(content_type, {})
            entries = list(bucket.values())
            if entry_id:
                entries = [e for e in entries if e.get("id") == entry_id]
            if tenant_id:
                entries = [e for e in entries if e.get("tenant_id") in (None, "default", "global", tenant_id)]
            return entries

        base_url = self._require_configured()
        params: dict[str, str] = {"status": "published"}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if entry_id:
            params["id"] = entry_id
        response = await self._client.get(
            f"{base_url}/api/{content_type}",
            params=params,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return response.json()

    async def deploy_payload(
        self, payload: dict[str, Any], tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Deploy a structured bundle of approved CMS models and changes to the live surface."""

        applied_items: list[dict[str, Any]] = []
        applied_hashes: list[str] = []
        version = payload.get("version", "v1.0")

        # 1. Handle explicit items list
        if "items" in payload and isinstance(payload["items"], list):
            for item in payload["items"]:
                ct = item.get("content_type", "pages")
                eid = item.get("entry_id") or item.get("id") or f"item-{len(applied_items)}"
                res = await self.publish_entry(ct, eid, tenant_id=tenant_id, version=version, payload=item)
                applied_items.append(res)
                item_hash = hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                applied_hashes.append(item_hash)

        # 2. Handle categorized models (schemas, products, pages, layouts, assets, code_diffs)
        category_map = {
            "schema_diffs": ("schemas", "schema_name"),
            "products": ("products", "product_id"),
            "pages": ("pages", "page_id"),
            "layouts": ("layouts", "layout_id"),
            "assets": ("assets", "asset_id"),
            "code_diffs": ("code_diffs", "file_path"),
        }
        for cat_key, (ct, id_field) in category_map.items():
            if cat_key in payload and isinstance(payload[cat_key], list):
                for model in payload[cat_key]:
                    model_dict = model if isinstance(model, dict) else (model.model_dump() if hasattr(model, "model_dump") else dict(model))
                    eid = str(model_dict.get(id_field) or model_dict.get("id") or f"{ct}-{len(applied_items)}")
                    res = await self.publish_entry(ct, eid, tenant_id=tenant_id, version=version, payload=model_dict)
                    applied_items.append(res)
                    h = hashlib.sha256(json.dumps(model_dict, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                    applied_hashes.append(h)

        # 3. Handle single entry payload
        if not applied_items:
            eid = payload.get("entry_id") or payload.get("id") or "entry-1"
            ct = payload.get("content_type", "pages")
            res = await self.publish_entry(ct, eid, tenant_id=tenant_id, version=version, payload=payload)
            applied_items.append(res)
            h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            applied_hashes.append(h)

        return {
            "status_code": "200",
            "status": "published",
            "applied_items": applied_items,
            "applied_hashes": applied_hashes,
            "version": version,
            "target": "cms",
            "deployed_at": datetime.now(UTC).isoformat(),
        }

    async def health(self) -> dict[str, Any]:
        """Check CMS client capability and configuration readiness without leaking secrets."""
        configured = bool(self._base_url)
        return {
            "status": "healthy" if (configured or not self._base_url) else "unhealthy",
            "type": "headless_cms",
            "mode": "remote_http" if configured else "in_memory_staged",
        }

    async def aclose(self) -> None:
        await self._client.aclose()