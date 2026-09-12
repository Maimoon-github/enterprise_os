"""Persists promoted brand knowledge, heuristics, and model deltas.

The source architecture describes an Institutional Memory Store without
specifying its record shape, so ``MemoryRecord`` is defined here as the
minimal contract ``app.services.memory_promotion`` needs to promote a
validated learning delta.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table

_table = standard_table("institutional_memory", metadata)


class MemoryRecord(BaseModel):
    """A single piece of promoted, validated institutional knowledge."""

    memory_id: str
    tenant_id: str
    category: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_task_ids: list[str] = Field(default_factory=list)
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryRepository(BaseJsonRepository[MemoryRecord]):
    """Persists promoted ``MemoryRecord`` entries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: MemoryRecord.model_validate(doc),
        )

    async def promote(self, record: MemoryRecord) -> None:
        await self.save(record.memory_id, record.tenant_id, record)

    async def list_by_tenant(
        self, tenant_id: str, category: str | None = None
    ) -> list[MemoryRecord]:
        """Return all memory records for ``tenant_id``, optionally filtered by ``category``."""
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
        return records