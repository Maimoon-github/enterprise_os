"""Real PostgreSQL/pgvector persistence staging and process-restart resilience test.

Validates that:
1. Real PostgreSQL 16 with pgvector extension powers all repository implementations.
2. Versioned SQL migrations 0001-0007 are idempotently applied.
3. Process restart mid-workflow: backend connection pool disposed, provisioner daemon restarted.
4. CTS task states, W3C PROV audit chains, institutional memory, telemetry receipts,
   and provisioner replay state survive process restart and successfully complete to terminal state.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.settings import DatabaseSettings
from app.integrations.sandbox.provisioner_daemon import (
    ReplayStateManager,
    SandboxProvisionerEngine,
)
from app.persistence.database import Database
from app.persistence.repositories.artifact import ArtifactRepository
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.provenance import ProvenanceRepository
from app.persistence.repositories.task_state import TaskStateRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.memory import MemoryNamespace, MemoryRecord
from app.schemas.provenance import ProvenanceRecord
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxInvocationMandate,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType


POSTGRES_DSN = "postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend"


@pytest.mark.asyncio
async def test_real_postgresql_persistence_and_process_restart_resilience(tmp_path: Path) -> None:
    """Execute multi-stage workflow on real PostgreSQL, crash/restart backend and provisioner,
    and verify all state recovers with mathematical and cryptographic integrity."""
    tenant_id = f"tenant-staging-{uuid.uuid4().hex[:6]}"
    directive_id = f"dir-live-{uuid.uuid4().hex[:6]}"
    task_id_1 = f"task-cts-{uuid.uuid4().hex[:6]}"
    task_id_2 = f"task-cts-{uuid.uuid4().hex[:6]}"
    replay_file = tmp_path / "replay_state.json"

    # =========================================================================
    # PHASE 1: Real Database Connection & Migration Application
    # =========================================================================
    db_settings = DatabaseSettings(
        dsn=POSTGRES_DSN,
        enforce_rls=False,
        require_non_privileged_role=False,
    )
    db = Database(db_settings)

    # 1. Healthcheck and pgvector extension verification
    health = await db.healthcheck()
    assert health["status"] == "healthy", f"Database unhealthy: {health}"
    assert health["extensions"].get("vector") is True, "pgvector extension must be active"

    # 2. Apply all Layer-4 migrations idempotently
    await db.apply_migrations()

    # 3. Instantiate real PostgreSQL repositories
    op_repo = OperationalRepository(db.session_factory)
    ts_repo = TaskStateRepository(db.session_factory)
    prov_repo = ProvenanceRepository(db.session_factory)
    mem_repo = MemoryRepository(db.session_factory)
    tel_repo = TelemetryRepository(db.session_factory)
    art_repo = ArtifactRepository(db.session_factory)

    # 4. Instantiate provisioner engine with persistent replay state
    provisioner_engine_1 = SandboxProvisionerEngine(
        replay_state_path=replay_file,
    )

    # =========================================================================
    # PHASE 2: Execute Pre-Restart Workflow Stages
    # =========================================================================
    # A. Persist Directive in PostgreSQL
    directive = Directive(
        directive_id=directive_id,
        tenant_id=tenant_id,
        objective="Deploy resilient enterprise payment tier with verified sandbox isolation",
        budget_cap=25000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(
            tenant_id=tenant_id,
            brand_ids=["brand-enterprise"],
            allowed_channels=["web"],
        ),
    )
    await op_repo.save_directive(directive)

    # B. Persist Initial CTS Task State (P1)
    task_state_1 = CanonicalTaskState(
        task_id=task_id_1,
        directive_id=directive_id,
        tenant_id=tenant_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.IN_PROGRESS,
        version=1,
    )
    await ts_repo.save_state(tenant_id, task_state_1)

    # C. Record W3C PROV Ledger Audit Block 1
    prov_rec_1 = await prov_repo.append(
        tenant_id=tenant_id,
        entity_id=task_id_1,
        activity="TASK_DISPATCH_STRATEGY",
        agent="W_STRAT",
        metadata={"step": "P1", "budget_allocated": 5000.0},
    )
    assert prov_rec_1.record_hash is not None

    # D. Execute Physical Specialist Attempt 1 via Provisioner
    exec_id_1 = f"exec-stg-01-{uuid.uuid4().hex[:6]}"
    mandate_1 = SandboxInvocationMandate(
        execution_id=exec_id_1,
        task_id=task_id_1,
        tenant_id=tenant_id,
        stage_attempt_id="att-stg-01",
        worker_role="W_STRAT",
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 5000.0, "channels": ["web"], "constraints": {"min_allocation": 100.0}},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
    )
    result_1 = provisioner_engine_1.execute(mandate_1)
    assert result_1.success is True
    assert result_1.execution_receipt is not None

    # E. Store Promoted Institutional Memory
    mem_record = MemoryRecord(
        memory_id=f"mem-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        category="pricing",
        statement="optimal price is 49.0 with 0.18 lift projection",
        namespace=MemoryNamespace.ATTRIBUTION_HEURISTICS.value,
        title="pricing_tier_conversion_curve",
        confidence=0.92,
        metadata={"optimal_price": 49.0, "lift_projection": 0.18, "source_execution_id": exec_id_1},
    )
    await mem_repo.promote(mem_record)

    # F. Ingest Telemetry Event
    tel_event = TelemetryEvent(
        event_id=f"tel-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        event_type=TelemetryEventType.TRAFFIC,
        channel="web",
        occurred_at=datetime.now(UTC),
        metrics={"duration_ms": float(result_1.execution_duration_ms), "cpu_cores": 1.0},
    )
    await tel_repo.record(tel_event)

    # =========================================================================
    # PHASE 3: SIMULATE PROCESS CRASH & RESTART
    # =========================================================================
    # 1. Dispose database connection pool (simulates backend daemon crash)
    await db.dispose()

    # 2. Verify replay state file was flushed to disk
    assert replay_file.exists(), "Replay manager must flush state to disk"

    # 3. Simulate new backend process starting up with fresh database pool
    db_restarted = Database(db_settings)
    op_repo_2 = OperationalRepository(db_restarted.session_factory)
    ts_repo_2 = TaskStateRepository(db_restarted.session_factory)
    prov_repo_2 = ProvenanceRepository(db_restarted.session_factory)
    mem_repo_2 = MemoryRepository(db_restarted.session_factory)
    tel_repo_2 = TelemetryRepository(db_restarted.session_factory)

    # 4. Simulate new provisioner daemon process starting up from disk state
    provisioner_engine_2 = SandboxProvisionerEngine(
        replay_state_path=replay_file,
    )

    # =========================================================================
    # PHASE 4: Prove Complete State Recovery Across Restart
    # =========================================================================
    # A. Directive Survived Restart
    rec_directive = await op_repo_2.require(directive_id)
    assert rec_directive.directive_id == directive_id
    assert rec_directive.budget_cap == 25000.0

    # B. CTS Task State Survived Restart
    rec_task_1 = await ts_repo_2.require(task_id_1)
    assert rec_task_1.status == TaskStatus.IN_PROGRESS
    assert rec_task_1.version == 1

    # Atomic CAS update on recovered task state
    cas_success = await ts_repo_2.compare_and_swap_state(
        tenant_id=tenant_id,
        expected_version=1,
        state=CanonicalTaskState(
            task_id=task_id_1,
            directive_id=directive_id,
            tenant_id=tenant_id,
            worker_role=WorkerRole.STRATEGY,
            status=TaskStatus.COMPLETED,
            version=2,
        ),
    )
    assert cas_success is True

    # C. Replay Protection Survived Provisioner Daemon Restart
    with pytest.raises(Exception) as exc_info:
        provisioner_engine_2.execute(mandate_1)
    assert "Replay forbidden" in str(exc_info.value)

    # D. Provenance Cryptographic Hash Chain Survived Restart
    # Record Block 2 and verify it chains to Block 1 from pre-restart
    prov_rec_2 = await prov_repo_2.append(
        tenant_id=tenant_id,
        entity_id=task_id_2,
        activity="TASK_DISPATCH_CODE_SYNTHESIS",
        agent="W_DEV",
        metadata={"step": "P2", "preceding_task": task_id_1},
    )
    assert prov_rec_2.prev_record_hash == prov_rec_1.record_hash
    assert prov_rec_2.record_hash != prov_rec_1.record_hash

    # Verify chain integrity
    chain_records = await prov_repo_2.chain(tenant_id=tenant_id)
    assert len(chain_records) == 2
    assert chain_records[0].record_hash == prov_rec_1.record_hash
    assert chain_records[1].record_hash == prov_rec_2.record_hash
    assert await prov_repo_2.verify_chain(tenant_id=tenant_id) is True

    # E. Institutional Memory Survived Restart
    rec_mem = await mem_repo_2.get(mem_record.memory_id, tenant_id=tenant_id)
    assert rec_mem is not None
    assert rec_mem.title == "pricing_tier_conversion_curve"
    assert rec_mem.metadata["optimal_price"] == 49.0

    # F. Telemetry Survived Restart
    events = await tel_repo_2.query_range(
        tenant_id=tenant_id,
        event_type=TelemetryEventType.TRAFFIC.value,
    )
    assert len(events) >= 1
    assert events[0].event_id == tel_event.event_id

    # G. Execute Fresh Specialist Attempt 2 under Restarted Daemon
    exec_id_2 = f"exec-stg-02-{uuid.uuid4().hex[:6]}"
    mandate_2 = SandboxInvocationMandate(
        execution_id=exec_id_2,
        task_id=task_id_2,
        tenant_id=tenant_id,
        stage_attempt_id="att-stg-02",
        worker_role="W_DEV",
        capability=SandboxCapability.CODE,
        operation="run_script",
        payload={"script": "import sys; sys.stdout.write('{}')"},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
    )
    result_2 = provisioner_engine_2.execute(mandate_2)
    assert result_2.success is True

    # Complete Task 2 to terminal state
    await ts_repo_2.save_state(
        tenant_id,
        CanonicalTaskState(
            task_id=task_id_2,
            directive_id=directive_id,
            tenant_id=tenant_id,
            worker_role=WorkerRole.DEVELOPMENT,
            status=TaskStatus.COMPLETED,
            version=1,
        ),
    )
    final_task_2 = await ts_repo_2.require(task_id_2)
    assert final_task_2.status == TaskStatus.COMPLETED

    # Clean up connection pool
    await db_restarted.dispose()
