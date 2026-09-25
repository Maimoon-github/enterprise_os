"""Appends W3C PROV audit records.

Records are append-only and hash-chained per tenant: each new record's hash
covers the previous record's hash and optional metadata hash, so any retroactive
edit invalidates every subsequent record in the chain.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import standard_table
from app.schemas.provenance import ProvenanceRecord

_table = standard_table("provenance_records", metadata)


def _compute_metadata_hash(
    metadata: dict[str, Any] | None, w3c_prov: dict[str, Any] | None
) -> str | None:
    """Compute deterministic SHA-256 hash of structured metadata and W3C PROV graph."""
    if not metadata and not w3c_prov:
        return None
    payload = json.dumps(
        {"metadata": metadata or {}, "w3c_prov": w3c_prov or {}},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_hash(
    prev_hash: str | None,
    entity_id: str,
    activity: str,
    agent: str,
    occurred_at: datetime,
    metadata_hash: str | None = None,
) -> str:
    """Compute tamper-evident SHA-256 hash chaining entity, activity, agent, and metadata."""
    if metadata_hash:
        payload = f"{prev_hash or ''}|{entity_id}|{activity}|{agent}|{occurred_at.isoformat()}|{metadata_hash}"
    else:
        payload = f"{prev_hash or ''}|{entity_id}|{activity}|{agent}|{occurred_at.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProvenanceRepository:
    """Appends and reads the per-tenant provenance chain."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _latest(
        self, tenant_id: str, *, session: AsyncSession | None = None
    ) -> ProvenanceRecord | None:
        stmt = select(_table.c.document).where(_table.c.tenant_id == tenant_id)
        if session is not None:
            rows = await session.execute(stmt)
            documents = [doc for (doc,) in rows.all()]
        else:
            async with self._session_factory() as local_session:
                rows = await local_session.execute(stmt)
                documents = [doc for (doc,) in rows.all()]
        if not documents:
            return None
        records = [ProvenanceRecord.model_validate(doc) for doc in documents]
        return max(records, key=lambda record: record.occurred_at)

    async def append(
        self,
        *,
        tenant_id: str,
        entity_id: str,
        activity: str,
        agent: str,
        record_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        w3c_prov: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> ProvenanceRecord:
        """Append a new hash-chained provenance record and return it.

        Supports idempotent append and caller transaction participation.
        """
        # Idempotency check
        if record_id is not None:
            stmt = select(_table.c.document).where(
                _table.c.id == record_id, _table.c.tenant_id == tenant_id
            )
            if session is not None:
                row = await session.execute(stmt)
                existing_doc = row.scalar_one_or_none()
                if existing_doc:
                    return ProvenanceRecord.model_validate(existing_doc)
            else:
                async with self._session_factory() as local_session:
                    row = await local_session.execute(stmt)
                    existing_doc = row.scalar_one_or_none()
                    if existing_doc:
                        return ProvenanceRecord.model_validate(existing_doc)

        occurred_at = datetime.now(UTC)
        latest = await self._latest(tenant_id, session=session)
        prev_hash = latest.record_hash if latest else None
        meta_hash = _compute_metadata_hash(metadata, w3c_prov)
        record_hash = _compute_hash(prev_hash, entity_id, activity, agent, occurred_at, meta_hash)

        record = ProvenanceRecord(
            record_id=record_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            occurred_at=occurred_at,
            prev_record_hash=prev_hash,
            metadata_hash=meta_hash,
            record_hash=record_hash,
            metadata=metadata or {},
            w3c_prov=w3c_prov or {},
        )
        insert_stmt = _table.insert().values(
            id=record.record_id,
            tenant_id=tenant_id,
            document=record.model_dump(mode="json"),
            updated_at=occurred_at,
        )
        if session is not None:
            await session.execute(insert_stmt)
        else:
            async with self._session_factory() as local_session:
                await local_session.execute(insert_stmt)
                await local_session.commit()
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
            recomputed_meta_hash = _compute_metadata_hash(record.metadata, record.w3c_prov)
            expected = _compute_hash(
                prev_hash,
                record.entity_id,
                record.activity,
                record.agent,
                record.occurred_at,
                recomputed_meta_hash,
            )
            if expected != record.record_hash or record.prev_record_hash != prev_hash:
                return False
            prev_hash = record.record_hash
        return True