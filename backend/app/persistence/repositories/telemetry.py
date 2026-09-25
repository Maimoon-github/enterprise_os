"""Persists normalized timeseries and conversion records.

Backed by a TimescaleDB hypertable in production (unspecified concrete
setup; see ``docs/ASSUMPTIONS.md``); the table definition here is
hypertable-compatible (a plain time-indexed table) and works unmodified
against a non-Timescale PostgreSQL instance for local development.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RepositoryError
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

    async def record(
        self, event: TelemetryEvent, *, session: AsyncSession | None = None
    ) -> TelemetryEvent:
        """Persist event with idempotent deduplication by idempotency_key or event_id."""
        if not event.tenant_id or not event.tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not event.event_id or not event.event_id.strip():
            raise RepositoryError("Event ID cannot be empty.")

        # 1. Idempotency check via idempotency_key within tenant scope
        if event.idempotency_key:
            existing = await self.get_by_idempotency_key(
                event.tenant_id, event.idempotency_key, session=session
            )
            if existing is not None:
                return existing

        # 2. Check by event_id within tenant scope
        existing_event = await self.get(event.event_id, tenant_id=event.tenant_id, session=session)
        if existing_event is not None:
            return existing_event

        # 3. Persist (cross-tenant collisions will fail closed in BaseJsonRepository.save)
        await self.save(event.event_id, event.tenant_id, event, session=session)
        return event

    async def get_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
        *,
        session: AsyncSession | None = None,
    ) -> TelemetryEvent | None:
        """Find an existing telemetry event by its idempotency key within a tenant scope."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not idempotency_key or not idempotency_key.strip():
            return None

        stmt = select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
        if session is not None:
            rows = await session.execute(stmt)
            raw_docs = [doc for (doc,) in rows.all()]
        else:
            async with self._session_factory() as local_session:
                rows = await local_session.execute(stmt)
                raw_docs = [doc for (doc,) in rows.all()]

        for doc in raw_docs:
            if isinstance(doc, dict) and doc.get("idempotency_key") == idempotency_key:
                return TelemetryEvent.model_validate(doc)
        return None

    async def query_range(
        self,
        tenant_id: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_type: str | None = None,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> list[TelemetryEvent]:
        """Query telemetry events in a bounded time range with strict tenant scoping."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if limit <= 0:
            return []

        stmt = select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
        if session is not None:
            rows = await session.execute(stmt)
            raw_docs = [doc for (doc,) in rows.all()]
        else:
            async with self._session_factory() as local_session:
                rows = await local_session.execute(stmt)
                raw_docs = [doc for (doc,) in rows.all()]

        events: list[TelemetryEvent] = []
        for doc in raw_docs:
            if not isinstance(doc, dict):
                continue
            ev = TelemetryEvent.model_validate(doc)
            if event_type and ev.event_type.value != event_type:
                continue
            if start_time and ev.occurred_at < start_time:
                continue
            if end_time and ev.occurred_at > end_time:
                continue
            events.append(ev)

        # Order by occurred_at descending for deterministic recency
        events.sort(key=lambda e: (e.occurred_at, e.event_id), reverse=True)
        return events[:limit]

    async def list_by_type(
        self,
        tenant_id: str,
        event_type: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[TelemetryEvent]:
        """Return telemetry events for ``tenant_id`` filtered by event type."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")

        stmt = select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
        if session is not None:
            rows = await session.execute(stmt)
            events = [TelemetryEvent.model_validate(doc) for (doc,) in rows.all()]
        else:
            async with self._session_factory() as local_session:
                rows = await local_session.execute(stmt)
                events = [TelemetryEvent.model_validate(doc) for (doc,) in rows.all()]
        return [event for event in events if event.event_type.value == event_type]

    async def list_all(
        self, tenant_id: str, *, session: AsyncSession | None = None
    ) -> list[TelemetryEvent]:
        """Return all telemetry events for ``tenant_id``."""
        return await self.list_by_tenant(tenant_id, session=session)