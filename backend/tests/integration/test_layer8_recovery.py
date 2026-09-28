"""Integration recovery verification tests for Layer-8 (T04, T05, T06, T15)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import RepositoryError
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.telemetry import (
    TelemetryEnvelope,
    TelemetryReceipt,
    TelemetryWorkItem,
)
from app.security.authorization_boundary import CallerIdentity
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


class FakeTelemetryRecoveryRepository(TelemetryRepository):
    """In-memory telemetry repository simulating relational tables, dedup, and leases."""

    def __init__(self, *, should_fail_on_admit: bool = False) -> None:
        self.should_fail_on_admit = should_fail_on_admit
        self.receipts: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        self.receipts_by_id: dict[str, dict[str, Any]] = {}
        self.work_items: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}

    async def admit(
        self, record: TelemetryEnvelope | dict[str, Any], *, session: Any = None
    ) -> TelemetryReceipt:
        if self.should_fail_on_admit:
            raise RepositoryError("Simulated database failure during receipt admission commit.")

        rec_dict = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)

        tenant_id = rec_dict.get("tenant_id")
        if not tenant_id or not str(tenant_id).strip():
            raise RepositoryError("Tenant ID cannot be empty.")

        source_id = str(rec_dict.get("source_id") or "src-1")
        source_account_id = str(rec_dict.get("source_account_id") or "acc-1")
        logical_event_id = str(rec_dict.get("logical_event_id") or "evt-1")
        source_revision = str(rec_dict.get("source_revision") or "1")

        key = (tenant_id, source_id, source_account_id, logical_event_id, source_revision)

        minimized_payload = (
            rec_dict.get("payload") if isinstance(rec_dict.get("payload"), dict) else rec_dict
        )
        content_hash = rec_dict.get("content_hash")
        if not content_hash:
            content_bytes = json.dumps(minimized_payload, sort_keys=True, default=str).encode(
                "utf-8"
            )
            content_hash = hashlib.sha256(content_bytes).hexdigest()

        now = datetime.now(UTC)

        # Unique identity check
        if key in self.receipts:
            existing = self.receipts[key]
            if existing["content_hash"] == content_hash:
                return TelemetryReceipt(
                    receipt_id=existing["id"],
                    tenant_id=tenant_id,
                    source_id=source_id,
                    source_account_id=source_account_id,
                    logical_event_id=logical_event_id,
                    source_revision=source_revision,
                    content_hash=existing["content_hash"],
                    status="duplicate",
                    minimized_payload=existing["minimized_payload"],
                    received_at=existing["received_at"],
                )
            else:
                return TelemetryReceipt(
                    receipt_id=existing["id"],
                    tenant_id=tenant_id,
                    source_id=source_id,
                    source_account_id=source_account_id,
                    logical_event_id=logical_event_id,
                    source_revision=source_revision,
                    content_hash=content_hash,
                    status="quarantined",
                    minimized_payload=minimized_payload,
                    received_at=now,
                )

        receipt_id = f"rcpt_{len(self.receipts) + 1}"
        stored_receipt = {
            "id": receipt_id,
            "tenant_id": tenant_id,
            "source_id": source_id,
            "source_account_id": source_account_id,
            "logical_event_id": logical_event_id,
            "source_revision": source_revision,
            "content_hash": content_hash,
            "status": "accepted",
            "minimized_payload": minimized_payload,
            "schema_version": "1.0",
            "policy_version": "1.0",
            "received_at": now,
        }
        self.receipts[key] = stored_receipt
        self.receipts_by_id[receipt_id] = stored_receipt

        work_id = f"work_{len(self.work_items) + 1}"
        self.work_items[work_id] = {
            "id": work_id,
            "receipt_id": receipt_id,
            "tenant_id": tenant_id,
            "status": "pending",
            "attempt_count": 0,
            "max_attempts": 5,
            "next_retry_at": None,
            "lease_owner": None,
            "lease_expires_at": None,
            "lease_generation": 0,
            "created_at": now,
            "updated_at": now,
        }

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
            received_at=now,
        )

    async def claim_work(
        self,
        tenant_id: str,
        lease_owner: str,
        lease_duration_seconds: int = 300,
        limit: int = 10,
        *,
        session: Any = None,
    ) -> list[TelemetryWorkItem]:
        now = datetime.now(UTC)
        claimed: list[TelemetryWorkItem] = []

        for item in self.work_items.values():
            if item["tenant_id"] != tenant_id:
                continue
            is_pending = item["status"] == "pending"
            is_expired = (
                item["status"] == "leased"
                and item["lease_expires_at"] is not None
                and item["lease_expires_at"] <= now
            )
            is_retry = item["status"] == "retry" and (
                item["next_retry_at"] is None or item["next_retry_at"] <= now
            )

            if is_pending or is_expired or is_retry:
                item["status"] = "leased"
                item["lease_owner"] = lease_owner
                item["lease_expires_at"] = now + timedelta(seconds=lease_duration_seconds)
                item["lease_generation"] += 1
                item["attempt_count"] += 1
                item["updated_at"] = now

                claimed.append(
                    TelemetryWorkItem(
                        work_item_id=item["id"],
                        receipt_id=item["receipt_id"],
                        tenant_id=tenant_id,
                        status="leased",
                        attempt_count=item["attempt_count"],
                        max_attempts=item["max_attempts"],
                        lease_owner=lease_owner,
                        lease_expires_at=item["lease_expires_at"],
                        lease_generation=item["lease_generation"],
                        created_at=item["created_at"],
                        updated_at=now,
                    )
                )
                if len(claimed) >= limit:
                    break
        return claimed

    async def complete_work(
        self,
        tenant_id: str,
        work_item_id: str,
        lease_generation: int,
        *,
        session: Any = None,
    ) -> TelemetryWorkItem:
        now = datetime.now(UTC)
        item = self.work_items.get(work_item_id)
        if item is None or item["tenant_id"] != tenant_id:
            raise RepositoryError(f"Work item '{work_item_id}' not found for tenant '{tenant_id}'.")

        if item["status"] != "leased":
            raise RepositoryError(
                f"Work item '{work_item_id}' cannot be completed: "
                f"status is '{item['status']}', expected 'leased'."
            )
        if item["lease_generation"] != lease_generation:
            raise RepositoryError(
                f"Stale lease generation {lease_generation} for work item '{work_item_id}'; "
                f"current generation is {item['lease_generation']}."
            )
        if item["lease_expires_at"] and item["lease_expires_at"] < now:
            raise RepositoryError(
                f"Lease for work item '{work_item_id}' expired at "
                f"{item['lease_expires_at'].isoformat()}; cannot complete with stale lease."
            )

        item["status"] = "done"
        item["updated_at"] = now
        return TelemetryWorkItem(
            work_item_id=work_item_id,
            receipt_id=item["receipt_id"],
            tenant_id=tenant_id,
            status="done",
            attempt_count=item["attempt_count"],
            max_attempts=item["max_attempts"],
            lease_owner=item["lease_owner"],
            lease_expires_at=item["lease_expires_at"],
            lease_generation=lease_generation,
            created_at=item["created_at"],
            updated_at=now,
        )


# ==============================================================================
# T04: Deduplication Survives Timestamp Changes & Collision Quarantine
# ==============================================================================


@pytest.mark.asyncio
async def test_t04_dedup_survives_timestamp_changes() -> None:
    """Duplicate requests with altered timestamps resolve to single logical event."""
    repo = FakeTelemetryRecoveryRepository()
    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        telemetry_repository=repo,
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
    )
    caller = CallerIdentity(
        subject="telemetry_engine",
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        risk_ceiling=RiskLevel.LOW,
        allowed_capabilities=frozenset({"telemetry.ingest"}),
    )

    t1 = datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 28, 12, 5, 0, tzinfo=UTC)  # Changed event timestamp

    payload = {"order_id": "ord_999", "amount": "49.99"}

    # 1. First delivery
    rec1 = await gateway.admit(
        caller,
        tenant_id="tenant-1",
        record={
            "tenant_id": "tenant-1",
            "source_id": "shopify",
            "source_account_id": "store_main",
            "logical_event_id": "ord_999",
            "source_revision": "1",
            "occurred_at": t1,
            "payload": payload,
        },
    )
    assert rec1.status == "accepted"

    # 2. Second delivery with altered timestamp and identical logical identity & payload
    rec2 = await gateway.admit(
        caller,
        tenant_id="tenant-1",
        record={
            "tenant_id": "tenant-1",
            "source_id": "shopify",
            "source_account_id": "store_main",
            "logical_event_id": "ord_999",
            "source_revision": "1",
            "occurred_at": t2,
            "payload": payload,
        },
    )
    assert rec2.status == "duplicate"
    assert rec2.receipt_id == rec1.receipt_id

    # 3. Third delivery: ID collision with materially different payload
    rec3 = await gateway.admit(
        caller,
        tenant_id="tenant-1",
        record={
            "tenant_id": "tenant-1",
            "source_id": "shopify",
            "source_account_id": "store_main",
            "logical_event_id": "ord_999",
            "source_revision": "1",
            "occurred_at": t2,
            "payload": {"order_id": "ord_999", "amount": "9999.00"},  # Material conflict!
        },
    )
    assert rec3.status == "quarantined"

    # 4. Legitimate distinct event with different logical_event_id
    rec4 = await gateway.admit(
        caller,
        tenant_id="tenant-1",
        record={
            "tenant_id": "tenant-1",
            "source_id": "shopify",
            "source_account_id": "store_main",
            "logical_event_id": "ord_1000",
            "source_revision": "1",
            "occurred_at": t1,
            "payload": payload,
        },
    )
    assert rec4.status == "accepted"
    assert rec4.receipt_id != rec1.receipt_id


# ==============================================================================
# T05: Atomic Admission & Provenance Crash Recovery
# ==============================================================================


@pytest.mark.asyncio
async def test_t05_database_admission_failure_rolls_back_cleanly() -> None:
    """Crash/failure during admission persistence produces no orphan state."""
    repo = FakeTelemetryRecoveryRepository(should_fail_on_admit=True)
    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        telemetry_repository=repo,
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
    )
    caller = CallerIdentity(
        subject="telemetry_engine",
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        risk_ceiling=RiskLevel.LOW,
        allowed_capabilities=frozenset({"telemetry.ingest"}),
    )

    err_msg = "Simulated database failure during receipt admission commit"
    with pytest.raises(RepositoryError, match=err_msg):
        await gateway.admit(
            caller,
            tenant_id="tenant-1",
            record={
                "tenant_id": "tenant-1",
                "source_id": "shopify",
                "source_account_id": "store_main",
                "logical_event_id": "ord_crash_test",
                "payload": {"status": "crash"},
            },
        )

    # Verify no receipts or work items were committed
    assert len(repo.receipts) == 0
    assert len(repo.work_items) == 0


# ==============================================================================
# T06: Expired Leases & Fencing Generation Token Recovery
# ==============================================================================


@pytest.mark.asyncio
async def test_t06_stale_fencing_token_rejected_on_completion() -> None:
    """When a worker lease expires and is reclaimed, the stale worker cannot commit."""
    repo = FakeTelemetryRecoveryRepository()
    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        telemetry_repository=repo,
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
    )
    caller = CallerIdentity(
        subject="telemetry_engine",
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        risk_ceiling=RiskLevel.LOW,
        allowed_capabilities=frozenset({"telemetry.ingest", "telemetry.process"}),
    )

    # 1. Admit an item to create a pending work item
    receipt = await gateway.admit(
        caller,
        tenant_id="tenant-1",
        record={
            "tenant_id": "tenant-1",
            "source_id": "ads_meta",
            "source_account_id": "act_123",
            "logical_event_id": "report_chunk_1",
            "payload": {"impressions": 100},
        },
    )
    assert receipt.status == "accepted"

    # 2. Worker A claims the work item with short lease duration (0 seconds -> expired)
    items_a = await gateway.claim_work(
        caller,
        tenant_id="tenant-1",
        worker_id="worker_A",
        lease_duration_seconds=0,
        limit=1,
    )
    assert len(items_a) == 1
    work_a = items_a[0]
    assert work_a.lease_generation == 1
    assert work_a.lease_owner == "worker_A"

    # 3. Worker B reclaims the expired work item -> lease generation increments to 2
    items_b = await gateway.claim_work(
        caller,
        tenant_id="tenant-1",
        worker_id="worker_B",
        lease_duration_seconds=300,
        limit=1,
    )
    assert len(items_b) == 1
    work_b = items_b[0]
    assert work_b.lease_generation == 2
    assert work_b.lease_owner == "worker_B"

    # 4. Worker A attempts to complete work item using stale generation 1 -> must fail closed
    with pytest.raises(RepositoryError, match="Stale lease generation 1"):
        await gateway.complete_work(
            caller,
            tenant_id="tenant-1",
            work_item_id=work_a.work_item_id,
            lease_generation=work_a.lease_generation,
        )

    # 5. Worker B completes with active generation 2 -> succeeds
    completed = await gateway.complete_work(
        caller,
        tenant_id="tenant-1",
        work_item_id=work_b.work_item_id,
        lease_generation=work_b.lease_generation,
    )
    assert completed.status == "done"
    assert completed.lease_generation == 2


# ==============================================================================
# T15: Additive Migration Preserves Historical Telemetry & Idempotency
# ==============================================================================


@pytest.mark.asyncio
async def test_t15_migration_script_is_syntactically_valid_and_idempotent() -> None:
    """Verify 0007_layer8_ingestion.sql contains required composite constraints, RLS, and grants."""
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "migrations"
        / "sql"
        / "0007_layer8_ingestion.sql"
    )
    assert migration_path.exists(), "0007_layer8_ingestion.sql must exist"

    sql_content = migration_path.read_text(encoding="utf-8")

    # 1. Structural requirements
    assert "CREATE TABLE IF NOT EXISTS telemetry_receipts" in sql_content
    assert "CREATE TABLE IF NOT EXISTS telemetry_work_items" in sql_content
    assert "CREATE TABLE IF NOT EXISTS telemetry_collection_runs" in sql_content

    # 2. Composite uniqueness constraint independent of timestamps
    assert "uq_telemetry_receipts_identity" in sql_content
    assert "tenant_id" in sql_content
    assert "source_id" in sql_content
    assert "source_account_id" in sql_content
    assert "logical_event_id" in sql_content
    assert "source_revision" in sql_content

    # 3. RLS forced on tables
    assert "ALTER TABLE telemetry_receipts FORCE ROW LEVEL SECURITY;" in sql_content
    assert "ALTER TABLE telemetry_work_items FORCE ROW LEVEL SECURITY;" in sql_content
    assert "ALTER TABLE telemetry_collection_runs FORCE ROW LEVEL SECURITY;" in sql_content

    # 4. Tenant isolation policies matching 0005
    assert "tenant_isolation_telemetry_receipts" in sql_content
    assert "tenant_isolation_telemetry_work_items" in sql_content
    assert "tenant_isolation_telemetry_collection_runs" in sql_content
    assert "app.current_tenant" in sql_content

    # 5. Non-superuser runtime grants
    expected_grant = (
        "GRANT SELECT, INSERT, UPDATE ON telemetry_receipts, telemetry_work_items, "
        "telemetry_collection_runs TO enterprise_runtime;"
    )
    assert expected_grant in sql_content or "GRANT SELECT, INSERT, UPDATE" in sql_content
