"""Persists promoted brand knowledge, heuristics, and model deltas.

The source architecture describes an Institutional Memory Store without
specifying its record shape, so ``MemoryRecord`` is defined here as the
minimal contract ``app.services.memory_promotion`` needs to promote a
validated learning delta.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from enum import StrEnum
from typing import Any


class MemoryNamespace(StrEnum):
    """Namespaces for durable institutional knowledge."""

    BRAND_RULES = "brand_rules"
    ATTRIBUTION_HEURISTICS = "attribution_heuristics"
    REGULATORY_POLICIES = "regulatory_policies"
    NEGATIVE_CONSTRAINTS = "negative_constraints"
    PRODUCT_SPECS = "product_specs"
    GENERAL = "general"


class MemoryRecord(BaseModel):
    """A single piece of promoted, validated institutional knowledge."""

    memory_id: str
    tenant_id: str
    category: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    namespace: str = "brand_rules"
    brand_id: str | None = None
    title: str = ""
    promoted_by: str = "system"
    promotion_justification: str = ""
    provenance_ref: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_task_ids: list[str] = Field(default_factory=list)
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table

_table = standard_table("institutional_memory", metadata)


class MemoryRepository(BaseJsonRepository[MemoryRecord]):
    """Persists promoted ``MemoryRecord`` entries with validation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: MemoryRecord.model_validate(doc),
        )

    async def promote(self, record: MemoryRecord, min_confidence: float = 0.6) -> None:
        """Promote a validated memory record to long-term storage."""
        if record.confidence < min_confidence:
            raise ValueError(
                f"Memory record confidence {record.confidence:.2f} is below required threshold {min_confidence:.2f}"
            )
        await self.save(record.memory_id, record.tenant_id, record)

    async def list_by_tenant(
        self,
        tenant_id: str,
        category: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        """Return all memory records for ``tenant_id``, optionally filtered by ``category`` or ``namespace``."""
        if self._session_factory is None:
            return []
        from sqlalchemy import select

        async with self._session_factory() as session:
            rows = await session.execute(
                select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
            )
            records = [MemoryRecord.model_validate(doc) for (doc,) in rows.all()]
        if category is not None:
            records = [r for r in records if r.category == category]
        if namespace is not None:
            records = [r for r in records if r.namespace == namespace]
        return records