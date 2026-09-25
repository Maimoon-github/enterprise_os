"""Storage health aggregation service for Layer-4 systems of record.

Aggregates readiness for required Layer-4 storage dependencies (Database,
Artifact Store, Headless CMS, Provenance) without exposing credentials,
tenant records, hashes, or internal object locations.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StorageHealthAggregator:
    """Aggregates readiness for required Layer-4 storage dependencies."""

    def __init__(
        self,
        database: Any | None = None,
        artifact_store: Any | None = None,
        cms_client: Any | None = None,
        provenance_recorder: Any | None = None,
    ) -> None:
        self._database = database
        self._artifact_store = artifact_store
        self._cms_client = cms_client
        self._provenance_recorder = provenance_recorder

    async def check_health(self) -> dict[str, Any]:
        """Aggregate health across stores without exposing credentials or tenant records."""
        components: dict[str, Any] = {}
        overall_healthy = True

        # 1. PostgreSQL Database (CDB & MEM state)
        if self._database is not None and hasattr(self._database, "healthcheck"):
            try:
                db_res = await self._database.healthcheck()
                status = db_res.get("status", "unknown")
                components["database"] = {
                    "status": status,
                    "latency_ms": db_res.get("latency_ms"),
                    "extensions": db_res.get("extensions", {}),
                }
                if status != "healthy":
                    overall_healthy = False
            except Exception as exc:
                logger.debug("Database healthcheck failed: %s", exc)
                components["database"] = {"status": "unhealthy", "error": exc.__class__.__name__}
                overall_healthy = False
        else:
            components["database"] = {"status": "not_configured"}

        # 2. Artifact Store (ART payloads)
        if self._artifact_store is not None and hasattr(self._artifact_store, "health"):
            try:
                art_res = await self._artifact_store.health()
                status = art_res.get("status", "healthy")
                components["artifact_store"] = {
                    "status": status,
                    "type": art_res.get("type", "content_addressed_store"),
                    "object_count": art_res.get("object_count", 0),
                    "hash_algorithm": art_res.get("hash_algorithm", "SHA-256"),
                }
                if status != "healthy":
                    overall_healthy = False
            except Exception as exc:
                logger.debug("Artifact store healthcheck failed: %s", exc)
                components["artifact_store"] = {"status": "unhealthy", "error": exc.__class__.__name__}
                overall_healthy = False
        else:
            components["artifact_store"] = {"status": "not_configured"}

        # 3. Headless CMS Client
        if self._cms_client is not None and hasattr(self._cms_client, "health"):
            try:
                cms_res = await self._cms_client.health()
                status = cms_res.get("status", "healthy")
                components["cms"] = cms_res
                if status != "healthy":
                    overall_healthy = False
            except Exception as exc:
                logger.debug("CMS healthcheck failed: %s", exc)
                components["cms"] = {"status": "unhealthy", "error": exc.__class__.__name__}
                overall_healthy = False
        else:
            components["cms"] = {"status": "not_configured"}

        # 4. Provenance System
        components["provenance"] = {
            "status": "healthy" if self._provenance_recorder is not None else "not_configured",
            "append_only": True,
        }

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "layer": "Layer-4",
            "components": components,
        }
