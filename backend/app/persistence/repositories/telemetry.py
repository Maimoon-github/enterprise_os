"""Persists normalized timeseries and conversion records.

Backed by a TimescaleDB hypertable in production (unspecified concrete
setup; see ``docs/ASSUMPTIONS.md``); the table definition here is
hypertable-compatible (a plain time-indexed table) and works unmodified
against a non-Timescale PostgreSQL instance for local development.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.telemetry import TelemetryEvent

_table = standard_table("telemetry_events", metadata)


class TelemetryRepository(BaseJsonRepository[TelemetryEvent]):
    """Persists normalized ``TelemetryEvent`` records."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: TelemetryEvent.model_validate(doc),
        )

    async def record(self, event: TelemetryEvent) -> None:
        await self.save(event.event_id, event.tenant_id, event)

    async def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> TelemetryEvent | None:
        """Find an existing telemetry event by its idempotency key within a tenant scope."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
            )
            for (doc,) in rows.all():
                if isinstance(doc, dict) and doc.get("idempotency_key") == idempotency_key:
                    return TelemetryEvent.model_validate(doc)
            return None

    async def list_by_type(self, tenant_id: str, event_type: str) -> list[TelemetryEvent]:
        """Return telemetry events for ``tenant_id`` filtered by event type."""

        async with self._session_factory() as session:
            rows = await session.execute(
                select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
            )
            events = [TelemetryEvent.model_validate(doc) for (doc,) in rows.all()]
        return [event for event in events if event.event_type.value == event_type]

    async def list_all(self, tenant_id: str) -> list[TelemetryEvent]:
        """Return all telemetry events for ``tenant_id``."""
        return await self.list_by_tenant(tenant_id)