"""Persists normalized timeseries and conversion records.

Backed by a TimescaleDB hypertable in production (unspecified concrete
setup; see ``docs/ASSUMPTIONS.md``); the table definition here is
hypertable-compatible (a plain time-indexed table) and works unmodified
against a non-Timescale PostgreSQL instance for local development.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.types import JSON

from app.core.exceptions import RepositoryError
from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.telemetry import (
    RecordKind,
    TelemetryCollectionRun,
    TelemetryEnvelope,
    TelemetryEvent,
    TelemetryReceipt,
    TelemetryWorkItem,
)

_json_type = JSON().with_variant(JSONB, "postgresql")
_table = standard_table("telemetry_events", metadata)

_receipts_table = Table(
    "telemetry_receipts",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("source_id", String, nullable=False),
    Column("source_account_id", String, nullable=False),
    Column("logical_event_id", String, nullable=False),
    Column("source_revision", String, nullable=False, default="1"),
    Column("content_hash", String, nullable=False),
    Column("status", String, nullable=False, default="accepted"),
    Column("minimized_payload", _json_type, nullable=False),
    Column("schema_version", String, nullable=False, default="1.0"),
    Column("policy_version", String, nullable=False, default="1.0"),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "tenant_id",
        "source_id",
        "source_account_id",
        "logical_event_id",
        "source_revision",
        name="uq_telemetry_receipts_identity",
    ),
    extend_existing=True,
)

_work_items_table = Table(
    "telemetry_work_items",
    metadata,
    Column("id", String, primary_key=True),
    Column("receipt_id", String, ForeignKey("telemetry_receipts.id", ondelete="CASCADE"), nullable=False),
    Column("tenant_id", String, nullable=False, index=True),
    Column("status", String, nullable=False, default="pending"),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False, default=5),
    Column("next_retry_at", DateTime(timezone=True), nullable=True),
    Column("lease_owner", String, nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("lease_generation", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    extend_existing=True,
)

_runs_table = Table(
    "telemetry_collection_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("source_id", String, nullable=False),
    Column("query_fingerprint", String, nullable=False),
    Column("target_window_start", DateTime(timezone=True), nullable=False),
    Column("target_window_end", DateTime(timezone=True), nullable=False),
    Column("total_pages", Integer, nullable=False, default=0),
    Column("completed_pages", Integer, nullable=False, default=0),
    Column("coverage_ratio", Float, nullable=False, default=0.0),
    Column("generation", Integer, nullable=False, default=1),
    Column("status", String, nullable=False, default="running"),
    Column("published_revision", Integer, nullable=True),
    Column("document", _json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    extend_existing=True,
)


class TelemetryRepository(BaseJsonRepository[TelemetryEvent]):
    """Persists normalized ``TelemetryEvent`` records, receipts, and work items."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._receipts = _receipts_table
        self._work_items = _work_items_table
        self._runs = _runs_table
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

    async def admit(
        self,
        record: TelemetryEnvelope | dict[str, Any],
        *,
        session: AsyncSession | None = None,
    ) -> TelemetryReceipt:
        """Atomically admit a telemetry record with composite identity deduplication and work creation."""
        if hasattr(record, "model_dump"):
            rec_dict = record.model_dump(mode="json")
        else:
            rec_dict = dict(record)

        tenant_id = rec_dict.get("tenant_id")
        if not tenant_id or not str(tenant_id).strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        tenant_id = str(tenant_id).strip()

        source_id = str(rec_dict.get("source_id") or "default_source")
        source_account_id = str(rec_dict.get("source_account_id") or "default_account")
        source_revision = str(rec_dict.get("source_revision") or "1")

        # Determine stable logical_event_id
        logical_event_id = (
            rec_dict.get("source_event_id")
            or rec_dict.get("logical_event_id")
            or (rec_dict.get("payload", {}).get("logical_event_id") if isinstance(rec_dict.get("payload"), dict) else None)
            or rec_dict.get("record_id")
            or str(uuid.uuid4())
        )

        raw_payload = rec_dict.get("payload")
        minimized_payload: dict[str, Any] = dict(raw_payload) if isinstance(raw_payload, dict) else dict(rec_dict)

        # Deterministic content hash covering minimized payload and semantic fields
        content_bytes = json.dumps(minimized_payload, sort_keys=True, default=str).encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        now = datetime.now(UTC)
        schema_version = str(rec_dict.get("schema_version") or "1.0")
        policy_version = str(rec_dict.get("policy_version") or "1.0")

        async def _execute_admit(sess: AsyncSession) -> TelemetryReceipt:
            # Query existing receipt by composite identity
            stmt = select(self._receipts).where(
                and_(
                    self._receipts.c.tenant_id == tenant_id,
                    self._receipts.c.source_id == source_id,
                    self._receipts.c.source_account_id == source_account_id,
                    self._receipts.c.logical_event_id == logical_event_id,
                    self._receipts.c.source_revision == source_revision,
                )
            )
            res = await sess.execute(stmt)
            existing_row = res.fetchone()
            if existing_row is not None:
                # Deduplication check
                existing_hash = existing_row._mapping["content_hash"]
                if existing_hash == content_hash:
                    return TelemetryReceipt(
                        receipt_id=existing_row._mapping["id"],
                        tenant_id=tenant_id,
                        source_id=source_id,
                        source_account_id=source_account_id,
                        logical_event_id=logical_event_id,
                        source_revision=source_revision,
                        content_hash=existing_hash,
                        status="duplicate",
                        minimized_payload=existing_row._mapping["minimized_payload"],
                        schema_version=existing_row._mapping["schema_version"],
                        policy_version=existing_row._mapping["policy_version"],
                        received_at=existing_row._mapping["received_at"],
                    )
                else:
                    # Material difference under same identity -> quarantine
                    return TelemetryReceipt(
                        receipt_id=existing_row._mapping["id"],
                        tenant_id=tenant_id,
                        source_id=source_id,
                        source_account_id=source_account_id,
                        logical_event_id=logical_event_id,
                        source_revision=source_revision,
                        content_hash=content_hash,
                        status="quarantined",
                        minimized_payload=minimized_payload,
                        schema_version=schema_version,
                        policy_version=policy_version,
                        received_at=now,
                    )

            # Insert new receipt
            receipt_id = str(rec_dict.get("receipt_id") or uuid.uuid4())
            insert_receipt = self._receipts.insert().values(
                id=receipt_id,
                tenant_id=tenant_id,
                source_id=source_id,
                source_account_id=source_account_id,
                logical_event_id=logical_event_id,
                source_revision=source_revision,
                content_hash=content_hash,
                status="accepted",
                minimized_payload=minimized_payload,
                schema_version=schema_version,
                policy_version=policy_version,
                received_at=now,
                updated_at=now,
            )
            await sess.execute(insert_receipt)

            # Create corresponding work item atomically
            work_item_id = str(uuid.uuid4())
            insert_work = self._work_items.insert().values(
                id=work_item_id,
                receipt_id=receipt_id,
                tenant_id=tenant_id,
                status="pending",
                attempt_count=0,
                max_attempts=5,
                next_retry_at=None,
                lease_owner=None,
                lease_expires_at=None,
                lease_generation=0,
                created_at=now,
                updated_at=now,
            )
            await sess.execute(insert_work)

            return TelemetryReceipt(
                receipt_id=receipt_id,
                tenant_id=tenant_id,
                source_id=source_id,
                source_account_id=source_account_id,
                logical_event_id=logical_event_id,
                source_revision=source_revision,
                content_hash=content_hash,
                status="accepted",
                minimized_payload=minimized_payload,
                schema_version=schema_version,
                policy_version=policy_version,
                received_at=now,
            )

        if session is not None:
            return await _execute_admit(session)
        else:
            async with self._session_factory() as local_session:
                receipt = await _execute_admit(local_session)
                await local_session.commit()
                return receipt

    async def get_receipt(
        self, receipt_id: str, tenant_id: str, *, session: AsyncSession | None = None
    ) -> TelemetryReceipt | None:
        """Find an admitted receipt by ID within tenant scope."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        stmt = select(self._receipts).where(
            and_(self._receipts.c.id == receipt_id, self._receipts.c.tenant_id == tenant_id)
        )
        if session is not None:
            res = await session.execute(stmt)
            row = res.fetchone()
        else:
            async with self._session_factory() as local_session:
                res = await local_session.execute(stmt)
                row = res.fetchone()
        if row is None:
            return None
        return TelemetryReceipt(
            receipt_id=row._mapping["id"],
            tenant_id=row._mapping["tenant_id"],
            source_id=row._mapping["source_id"],
            source_account_id=row._mapping["source_account_id"],
            logical_event_id=row._mapping["logical_event_id"],
            source_revision=row._mapping["source_revision"],
            content_hash=row._mapping["content_hash"],
            status=row._mapping["status"],
            minimized_payload=row._mapping["minimized_payload"],
            schema_version=row._mapping["schema_version"],
            policy_version=row._mapping["policy_version"],
            received_at=row._mapping["received_at"],
        )

    async def claim_work(
        self,
        tenant_id: str,
        lease_owner: str,
        lease_duration_seconds: int = 300,
        limit: int = 10,
        *,
        session: AsyncSession | None = None,
    ) -> list[TelemetryWorkItem]:
        """Claim pending or expired work items with an expiring lease and incremented generation."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not lease_owner or not lease_owner.strip():
            raise RepositoryError("Lease owner must be specified.")

        now = datetime.now(UTC)
        lease_expires = now + timedelta(seconds=lease_duration_seconds)

        async def _execute_claim(sess: AsyncSession) -> list[TelemetryWorkItem]:
            stmt = (
                select(self._work_items)
                .where(
                    and_(
                        self._work_items.c.tenant_id == tenant_id,
                        or_(
                            self._work_items.c.status == "pending",
                            and_(
                                self._work_items.c.status == "leased",
                                self._work_items.c.lease_expires_at <= now,
                            ),
                            and_(
                                self._work_items.c.status == "retry",
                                or_(
                                    self._work_items.c.next_retry_at.is_(None),
                                    self._work_items.c.next_retry_at <= now,
                                ),
                            ),
                        ),
                    )
                )
                .limit(limit)
            )
            res = await sess.execute(stmt)
            rows = res.fetchall()
            claimed: list[TelemetryWorkItem] = []

            for r in rows:
                item_id = r._mapping["id"]
                current_gen = r._mapping["lease_generation"]
                new_gen = current_gen + 1
                attempts = r._mapping["attempt_count"] + 1

                upd = (
                    update(self._work_items)
                    .where(
                        and_(
                            self._work_items.c.id == item_id,
                            self._work_items.c.tenant_id == tenant_id,
                            self._work_items.c.lease_generation == current_gen,
                        )
                    )
                    .values(
                        status="leased",
                        lease_owner=lease_owner,
                        lease_expires_at=lease_expires,
                        lease_generation=new_gen,
                        attempt_count=attempts,
                        updated_at=now,
                    )
                )
                await sess.execute(upd)

                claimed.append(
                    TelemetryWorkItem(
                        work_item_id=item_id,
                        receipt_id=r._mapping["receipt_id"],
                        tenant_id=tenant_id,
                        status="leased",
                        attempt_count=attempts,
                        max_attempts=r._mapping["max_attempts"],
                        next_retry_at=r._mapping["next_retry_at"],
                        lease_owner=lease_owner,
                        lease_expires_at=lease_expires,
                        lease_generation=new_gen,
                        created_at=r._mapping["created_at"],
                        updated_at=now,
                    )
                )
            return claimed

        if session is not None:
            return await _execute_claim(session)
        else:
            async with self._session_factory() as local_session:
                res = await _execute_claim(local_session)
                await local_session.commit()
                return res

    async def complete_work(
        self,
        tenant_id: str,
        work_item_id: str,
        lease_generation: int,
        *,
        session: AsyncSession | None = None,
    ) -> TelemetryWorkItem:
        """Mark work item complete, failing closed if lease has expired or fencing generation is stale."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        now = datetime.now(UTC)

        async def _execute_complete(sess: AsyncSession) -> TelemetryWorkItem:
            stmt = select(self._work_items).where(
                and_(self._work_items.c.id == work_item_id, self._work_items.c.tenant_id == tenant_id)
            )
            res = await sess.execute(stmt)
            row = res.fetchone()
            if row is None:
                raise RepositoryError(f"Work item '{work_item_id}' not found for tenant '{tenant_id}'.")

            current_gen = row._mapping["lease_generation"]
            current_status = row._mapping["status"]
            current_expiry = row._mapping["lease_expires_at"]

            if current_status != "leased":
                raise RepositoryError(
                    f"Work item '{work_item_id}' cannot be completed: status is '{current_status}', expected 'leased'."
                )
            if current_gen != lease_generation:
                raise RepositoryError(
                    f"Stale lease generation {lease_generation} for work item '{work_item_id}'; current generation is {current_gen}."
                )
            if current_expiry and current_expiry < now:
                raise RepositoryError(
                    f"Lease for work item '{work_item_id}' expired at {current_expiry.isoformat()}; cannot complete work with stale lease."
                )

            upd = (
                update(self._work_items)
                .where(
                    and_(
                        self._work_items.c.id == work_item_id,
                        self._work_items.c.tenant_id == tenant_id,
                        self._work_items.c.lease_generation == lease_generation,
                    )
                )
                .values(status="done", updated_at=now)
            )
            await sess.execute(upd)

            return TelemetryWorkItem(
                work_item_id=work_item_id,
                receipt_id=row._mapping["receipt_id"],
                tenant_id=tenant_id,
                status="done",
                attempt_count=row._mapping["attempt_count"],
                max_attempts=row._mapping["max_attempts"],
                next_retry_at=row._mapping["next_retry_at"],
                lease_owner=row._mapping["lease_owner"],
                lease_expires_at=row._mapping["lease_expires_at"],
                lease_generation=lease_generation,
                created_at=row._mapping["created_at"],
                updated_at=now,
            )

        if session is not None:
            return await _execute_complete(session)
        else:
            async with self._session_factory() as local_session:
                res = await _execute_complete(local_session)
                await local_session.commit()
                return res

    async def checkpoint_collection_run(
        self,
        run: TelemetryCollectionRun,
        *,
        session: AsyncSession | None = None,
    ) -> TelemetryCollectionRun:
        """Persist or update collection run checkpoint state."""
        if not run.tenant_id or not run.tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        now = datetime.now(UTC)

        async def _execute_checkpoint(sess: AsyncSession) -> TelemetryCollectionRun:
            stmt = select(self._runs).where(
                and_(self._runs.c.id == run.run_id, self._runs.c.tenant_id == run.tenant_id)
            )
            res = await sess.execute(stmt)
            existing = res.fetchone()
            if existing is None:
                ins = self._runs.insert().values(
                    id=run.run_id,
                    tenant_id=run.tenant_id,
                    source_id=run.source_id,
                    query_fingerprint=run.query_fingerprint,
                    target_window_start=run.target_window_start,
                    target_window_end=run.target_window_end,
                    total_pages=run.total_pages,
                    completed_pages=run.completed_pages,
                    coverage_ratio=run.coverage_ratio,
                    generation=run.generation,
                    status=run.status,
                    published_revision=run.published_revision,
                    document=run.document,
                    created_at=now,
                    updated_at=now,
                )
                await sess.execute(ins)
            else:
                upd = (
                    update(self._runs)
                    .where(
                        and_(self._runs.c.id == run.run_id, self._runs.c.tenant_id == run.tenant_id)
                    )
                    .values(
                        completed_pages=run.completed_pages,
                        total_pages=run.total_pages,
                        coverage_ratio=run.coverage_ratio,
                        generation=run.generation,
                        status=run.status,
                        published_revision=run.published_revision,
                        document=run.document,
                        updated_at=now,
                    )
                )
                await sess.execute(upd)
            return run

        if session is not None:
            return await _execute_checkpoint(session)
        else:
            async with self._session_factory() as local_session:
                res = await _execute_checkpoint(local_session)
                await local_session.commit()
                return res

    async def commit_collection_run(
        self,
        tenant_id: str,
        run_id: str,
        expected_generation: int,
        published_revision: int,
        *,
        session: AsyncSession | None = None,
    ) -> TelemetryCollectionRun:
        """Commit completed collection run and publish revision, rejecting stale generations."""
        if not tenant_id or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        now = datetime.now(UTC)

        async def _execute_commit(sess: AsyncSession) -> TelemetryCollectionRun:
            stmt = select(self._runs).where(
                and_(self._runs.c.id == run_id, self._runs.c.tenant_id == tenant_id)
            )
            res = await sess.execute(stmt)
            row = res.fetchone()
            if row is None:
                raise RepositoryError(f"Collection run '{run_id}' not found.")
            if row._mapping["generation"] != expected_generation:
                raise RepositoryError(
                    f"Stale collection run generation {expected_generation}; current is {row._mapping['generation']}."
                )
            if row._mapping["coverage_ratio"] < 1.0 and row._mapping["completed_pages"] < row._mapping["total_pages"]:
                raise RepositoryError("Cannot commit collection run with incomplete page coverage.")

            upd = (
                update(self._runs)
                .where(
                    and_(
                        self._runs.c.id == run_id,
                        self._runs.c.tenant_id == tenant_id,
                        self._runs.c.generation == expected_generation,
                    )
                )
                .values(
                    status="completed",
                    published_revision=published_revision,
                    updated_at=now,
                )
            )
            await sess.execute(upd)
            return TelemetryCollectionRun(
                run_id=run_id,
                tenant_id=tenant_id,
                source_id=row._mapping["source_id"],
                query_fingerprint=row._mapping["query_fingerprint"],
                target_window_start=row._mapping["target_window_start"],
                target_window_end=row._mapping["target_window_end"],
                total_pages=row._mapping["total_pages"],
                completed_pages=row._mapping["completed_pages"],
                coverage_ratio=row._mapping["coverage_ratio"],
                generation=expected_generation,
                status="completed",
                published_revision=published_revision,
                document=row._mapping["document"],
                created_at=row._mapping["created_at"],
                updated_at=now,
            )

        if session is not None:
            return await _execute_commit(session)
        else:
            async with self._session_factory() as local_session:
                res = await _execute_commit(local_session)
                await local_session.commit()
                return res

    commit_report_run = commit_collection_run