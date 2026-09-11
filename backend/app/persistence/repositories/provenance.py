"""Appends W3C PROV audit records.

Records are append-only and hash-chained per tenant: each new record's hash
covers the previous record's hash, so any retroactive edit invalidates every
subsequent record in the chain.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import standard_table
from app.schemas.provenance import ProvenanceRecord

_table = standard_table("provenance_records", metadata)


def _compute_hash(
    prev_hash: str | None, entity_id: str, activity: str, agent: str, occurred_at: datetime
) -> str:
    payload = f"{prev_hash or ''}|{entity_id}|{activity}|{agent}|{occurred_at.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProvenanceRepository:
    """Appends and reads the per-tenant provenance chain."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _latest(self, tenant_id: str) -> ProvenanceRecord | None:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(_table.c.document).where(_table.c.tenant_id == tenant_id)
            )
            documents = [doc for (doc,) in rows.all()]
        if not documents:
            return None
        records = [ProvenanceRecord.model_validate(doc) for doc in documents]
        return max(records, key=lambda record: record.occurred_at)

    async def append(
        self, *, tenant_id: str, entity_id: str, activity: str, agent: str
    ) -> ProvenanceRecord:
        """Append a new hash-chained provenance record and return it."""

        occurred_at = datetime.now(UTC)
        latest = await self._latest(tenant_id)
        prev_hash = latest.record_hash if latest else None
        record_hash = _compute_hash(prev_hash, entity_id, activity, agent, occurred_at)

        record = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            occurred_at=occurred_at,
            prev_record_hash=prev_hash,
            record_hash=record_hash,
        )
        async with self._session_factory() as session:
            await session.execute(
                _table.insert().values(
                    id=record.record_id,
                    tenant_id=tenant_id,
                    document=record.model_dump(mode="json"),
                    updated_at=occurred_at,
                )
            )
            await session.commit()
        return record

    async def chain(self, tenant_id: str) -> list[ProvenanceRecord]:
        """Return the full, time-ordered provenance chain for ``tenant_id``."""

        async with self._session_factory() as session:
            rows = await session.execute(
                select(_table.c.document).where(_table.c.tenant_id == tenant_id)
            )
            records = [ProvenanceRecord.model_validate(doc) for (doc,) in rows.all()]
        return sorted(records, key=lambda record: record.occurred_at)

    def verify(self, records: list[ProvenanceRecord]) -> bool:
        """Return True if ``records`` (in order) form an unbroken hash chain."""

        prev_hash: str | None = None
        for record in records:
            expected = _compute_hash(
                prev_hash, record.entity_id, record.activity, record.agent, record.occurred_at
            )
            if expected != record.record_hash or record.prev_record_hash != prev_hash:
                return False
            prev_hash = record.record_hash
        return True