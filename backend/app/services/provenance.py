"""Records immutable entity/activity/agent audit lineage."""

from __future__ import annotations

from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.provenance import ProvenanceRecord


class ProvenanceRecorder:
    """Thin service boundary over ``ProvenanceRepository`` used by orchestration."""

    def __init__(self, repository: ProvenanceRepository) -> None:
        self._repository = repository

    async def record(
        self, *, tenant_id: str, entity_id: str, activity: str, agent: str
    ) -> ProvenanceRecord:
        """Append and return a new hash-chained provenance record."""

        return await self._repository.append(
            tenant_id=tenant_id, entity_id=entity_id, activity=activity, agent=agent
        )

    async def audit_chain(self, tenant_id: str) -> list[ProvenanceRecord]:
        """Return the full provenance chain for ``tenant_id``."""

        return await self._repository.chain(tenant_id)

    async def verify_chain(self, tenant_id: str) -> bool:
        """Return True if the persisted chain for ``tenant_id`` is intact."""

        chain = await self._repository.chain(tenant_id)
        return self._repository.verify(chain)