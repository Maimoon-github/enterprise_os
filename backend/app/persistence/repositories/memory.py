"""Persists promoted brand knowledge, heuristics, and model deltas.

Institutional Memory Store (MEM) maintains promoted, versioned, and immutable
institutional knowledge bound strictly to tenant boundaries.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RepositoryError
from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.memory import MemoryNamespace, MemoryRecord

__all__ = ["MemoryNamespace", "MemoryRecord", "MemoryRepository"]

_table = standard_table("institutional_memory", metadata)


class MemoryRepository(BaseJsonRepository[MemoryRecord]):
    """Persists promoted ``MemoryRecord`` entries with versioning and immutability."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: MemoryRecord.model_validate(doc),
        )

    async def promote(
        self,
        record: MemoryRecord,
        min_confidence: float = 0.6,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Promote a validated memory record to long-term storage.

        Enforces tenant binding, minimum confidence, immutable write-once identity,
        and version progression when superseding prior knowledge.
        """
        if not record.tenant_id or not isinstance(record.tenant_id, str) or not record.tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not record.memory_id or not isinstance(record.memory_id, str) or not record.memory_id.strip():
            raise RepositoryError("Memory ID cannot be empty.")

        if record.confidence < min_confidence:
            raise ValueError(
                f"Memory record confidence {record.confidence:.2f} is below required threshold {min_confidence:.2f}"
            )

        # 1. Immutable write-once check: never destructively overwrite an existing record_id
        existing = await self.get(record.memory_id, tenant_id=record.tenant_id, session=session)
        if existing is not None:
            raise RepositoryError(
                f"Memory record '{record.memory_id}' already exists and is immutable. Version progression required."
            )

        # 2. Version progression and supersedes linkage check
        if record.supersedes:
            sup_record = await self.get(record.supersedes, tenant_id=record.tenant_id, session=session)
            if sup_record is None:
                raise RepositoryError(
                    f"Superseded memory record '{record.supersedes}' not found for tenant '{record.tenant_id}'."
                )
            if record.version <= sup_record.version:
                raise ValueError(
                    f"Version progression violation: new version {record.version} must exceed superseded version {sup_record.version}."
                )
            # Deactivate superseded record within the same session/transaction
            sup_record.is_active = False
            await self.save(sup_record.memory_id, record.tenant_id, sup_record, session=session)

        # 3. Persist new record version
        await self.save(record.memory_id, record.tenant_id, record, session=session)

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        category: str | None = None,
        namespace: str | None = None,
        is_active: bool | None = None,
        session: AsyncSession | None = None,
    ) -> list[MemoryRecord]:
        """Return all memory records for ``tenant_id``, filtered by category, namespace, or active state."""
        records = await super().list_by_tenant(tenant_id, session=session)
        if category is not None:
            records = [r for r in records if r.category == category]
        if namespace is not None:
            records = [r for r in records if r.namespace == namespace]
        if is_active is not None:
            records = [r for r in records if r.is_active == is_active]
        return records