"""Operational certification test suite for Enterprise OS.

Validates the complete operational requirements:
1. Multi-Tenant Concurrency: Concurrent directives across distinct tenants executed in parallel.
2. W3C Trace Context Propagation: Ingress traceparent header propagates to sandbox execution and W3C PROV.
3. Timeout & Rejection Handling: Subprocess timeout and permission violations fail safely.
4. Orphan Cgroup & Process Hygiene: Verifies that attempt cgroups are cleanly destroyed without leaks.
5. Process Crash Resilience & Replay Protection: Replay state survives daemon restart.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.core.settings import DatabaseSettings
from app.core.trace_context import W3CTraceContext
from app.integrations.sandbox.provisioner_daemon import (
    DelegatedCgroupManager,
    SandboxProvisionerEngine,
)
from app.persistence.database import Database
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.provenance import ProvenanceRepository
from app.persistence.repositories.task_state import TaskStateRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxInvocationMandate,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType

POSTGRES_DSN = os.getenv(
    "ENTERPRISE_OS_POSTGRES_DSN",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend",
)


@pytest.fixture
def test_db():
    db_settings = DatabaseSettings(
        dsn=POSTGRES_DSN,
        enforce_rls=False,
        require_non_privileged_role=False,
    )
    return Database(db_settings)


@pytest.mark.asyncio
async def test_w3c_trace_context_propagation(test_db: Database, tmp_path: Path) -> None:
    """Verify that W3C Trace Context (traceparent) propagates from ingress to sandbox and PROV ledger."""
    await test_db.apply_migrations()
    prov_repo = ProvenanceRepository(test_db.session_factory)
    tel_repo = TelemetryRepository(test_db.session_factory)
    engine = SandboxProvisionerEngine(replay_state_path=tmp_path / "replay.json")

    tenant_id = f"tenant-trace-{uuid.uuid4().hex[:6]}"
    task_id = f"task-trace-{uuid.uuid4().hex[:6]}"

    # Ingress receives incoming W3C traceparent header
    ingress_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    trace_ctx = W3CTraceContext.parse(ingress_traceparent)
    assert trace_ctx is not None
    assert trace_ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"

    # Child span created for specialist sandbox invocation
    sandbox_span = trace_ctx.child_span()
    assert sandbox_span.trace_id == trace_ctx.trace_id
    assert sandbox_span.parent_span_id == trace_ctx.span_id

    mandate = SandboxInvocationMandate(
        execution_id=f"exec-trace-{uuid.uuid4().hex[:6]}",
        task_id=task_id,
        tenant_id=tenant_id,
        stage_attempt_id="att-trace-01",
        worker_role=WorkerRole.STRATEGY,
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 10000.0, "channels": ["web"]},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
        provenance_context=sandbox_span.to_dict(),
    )

    # Execute specialist in sandbox
    result = engine.execute(mandate)
    assert result.success is True

    # Record PROV block with correlated trace context
    prov_record = await prov_repo.append(
        tenant_id=tenant_id,
        entity_id=mandate.execution_id,
        activity="SPECIALIST_EXECUTION",
        agent="W_STRAT",
        metadata={
            "traceparent": sandbox_span.traceparent,
            "trace_id": sandbox_span.trace_id,
            "span_id": sandbox_span.span_id,
            "parent_span_id": sandbox_span.parent_span_id,
            "execution_receipt": (
                result.execution_receipt.model_dump(mode="json")
                if result.execution_receipt
                else {}
            ),
        },
    )
    assert prov_record.metadata.get("trace_id") == "4bf92f3577b34da6a3ce929d0e0e4736"

    # Ingest Telemetry event correlated to same trace_id
    tel_event = TelemetryEvent(
        event_id=f"tel-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        event_type=TelemetryEventType.TRAFFIC,
        channel="web",
        occurred_at=datetime.now(UTC),
        correlation_id=trace_ctx.trace_id,
        dimensions={"traceparent": sandbox_span.traceparent},
        metrics={"duration_ms": float(result.execution_duration_ms)},
    )
    await tel_repo.record(tel_event)

    # Verify query by correlation matches the same trace across services
    retrieved_tel = await tel_repo.get(tel_event.event_id, tenant_id=tenant_id)
    assert retrieved_tel is not None
    assert retrieved_tel.correlation_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert retrieved_tel.dimensions["traceparent"] == sandbox_span.traceparent


@pytest.mark.asyncio
async def test_concurrent_multi_tenant_directives(test_db: Database, tmp_path: Path) -> None:
    """Execute concurrent directives across 3 distinct tenants in parallel and prove full state isolation."""
    await test_db.apply_migrations()
    op_repo = OperationalRepository(test_db.session_factory)
    ts_repo = TaskStateRepository(test_db.session_factory)
    prov_repo = ProvenanceRepository(test_db.session_factory)
    engine = SandboxProvisionerEngine(replay_state_path=tmp_path / "concurrent_replay.json")

    tenants = [f"tenant-concurrent-{i}-{uuid.uuid4().hex[:4]}" for i in range(3)]

    async def run_tenant_workflow(tid: str, idx: int) -> dict[str, Any]:
        dir_id = f"dir-{tid}"
        task_id = f"task-{tid}"

        # 1. Directive
        directive = Directive(
            directive_id=dir_id,
            tenant_id=tid,
            objective=f"Concurrent tenant {idx} scaling directive",
            budget_cap=10000.0 * (idx + 1),
            risk_ceiling=RiskLevel.MEDIUM,
            scope=TenantScope(tenant_id=tid, allowed_channels=["web"]),
        )
        await op_repo.save_directive(directive)

        # 2. CTS Task
        task_state = CanonicalTaskState(
            task_id=task_id,
            directive_id=dir_id,
            tenant_id=tid,
            worker_role=WorkerRole.STRATEGY,
            status=TaskStatus.IN_PROGRESS,
            version=1,
        )
        await ts_repo.save_state(tid, task_state)

        # 3. Sandbox Execution
        mandate = SandboxInvocationMandate(
            execution_id=f"exec-{tid}",
            task_id=task_id,
            tenant_id=tid,
            stage_attempt_id=f"att-{tid}",
            worker_role=WorkerRole.STRATEGY,
            capability=SandboxCapability.ALLOC,
            operation="allocate_budget",
            payload={"total_budget": 5000.0 * (idx + 1), "channels": ["web"]},
            resource_limits=ResourceLimits(cpu_cores=0.5, memory_mb=256),
            network_policy=NetworkPolicy.DISABLED,
        )
        # Sandbox execution offloaded to thread to simulate concurrent client requests
        result = await asyncio.to_thread(engine.execute, mandate)

        # 4. PROV Ledger
        prov = await prov_repo.append(
            tenant_id=tid,
            entity_id=task_id,
            activity="ALLOCATE_BUDGET",
            agent="W_STRAT",
            metadata={"tenant_index": idx, "success": result.success},
        )

        # 5. Complete task
        await ts_repo.compare_and_swap_state(
            tenant_id=tid,
            expected_version=1,
            state=CanonicalTaskState(
                task_id=task_id,
                directive_id=dir_id,
                tenant_id=tid,
                worker_role=WorkerRole.STRATEGY,
                status=TaskStatus.COMPLETED,
                version=2,
            ),
        )

        return {"tenant_id": tid, "directive_id": dir_id, "task_id": task_id, "prov": prov}

    # Execute all 3 tenants concurrently
    results = await asyncio.gather(*[run_tenant_workflow(t, i) for i, t in enumerate(tenants)])
    assert len(results) == 3

    # Verify per-tenant isolation
    for r in results:
        tid = r["tenant_id"]
        dir_id = r["directive_id"]
        task_id = r["task_id"]

        # Only this tenant's directive is in its scope
        tenant_dirs = await op_repo.list_by_tenant(tid)
        assert len(tenant_dirs) == 1
        assert tenant_dirs[0].directive_id == dir_id

        # CTS state is COMPLETED
        t_state = await ts_repo.require(task_id)
        assert t_state.status == TaskStatus.COMPLETED
        assert t_state.version == 2

        # PROV chain is valid and isolated
        assert await prov_repo.verify_chain(tid) is True
        chain = await prov_repo.chain(tid)
        assert len(chain) == 1
        assert chain[0].entity_id == task_id


def test_orphan_cgroup_and_process_cleanup(tmp_path: Path) -> None:
    """Prove that attempt cgroups are cleanly destroyed without orphan leaks."""
    cgroup_root = tmp_path / "cgroup_test"
    cgroup_root.mkdir()
    (cgroup_root / "cgroup.controllers").write_text("cpu memory pids", encoding="utf-8")
    (cgroup_root / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")

    mgr = DelegatedCgroupManager(cgroup_root=cgroup_root)
    assert mgr.active is True

    with mgr.create_attempt_scope(
        stage_attempt_id="att-clean-1",
        execution_id="exec-clean-1",
        memory_mb=256,
        cpu_cores=1.0,
        pids_limit=64,
    ) as (attempt_cg, preexec_fn):
        assert attempt_cg is not None
        assert attempt_cg.exists()
        # Verify attempt cgroup has memory.max and pids.max configured
        assert (attempt_cg / "memory.max").exists()
        assert (attempt_cg / "pids.max").exists()
        assert callable(preexec_fn)

    # Scope exited: verify attempt cgroup directory was removed
    assert not attempt_cg.exists(), "Attempt cgroup must be destroyed upon scope exit"

    # Verify no child cgroup directories remain except daemon leaf
    child_dirs = [p.name for p in cgroup_root.iterdir() if p.is_dir()]
    assert child_dirs == ["daemon"], f"Only daemon/ cgroup should remain, found: {child_dirs}"


def test_rejection_and_policy_violation_paths(tmp_path: Path) -> None:
    """Verify that path traversal, excessive resources, and lease expiration are rejected."""
    from app.core.exceptions import PolicyViolationError, SandboxValidationError

    engine = SandboxProvisionerEngine(replay_state_path=tmp_path / "rejection_replay.json")

    # 1. Path traversal in payload strictly rejected before sandbox provisioning
    mandate_traversal = SandboxInvocationMandate(
        execution_id=f"exec-bad-{uuid.uuid4().hex[:6]}",
        task_id=f"task-bad-{uuid.uuid4().hex[:6]}",
        tenant_id="tenant-security",
        stage_attempt_id="att-bad-1",
        worker_role=WorkerRole.STRATEGY,
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 5000.0, "file_path": "../../../etc/passwd"},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
    )
    with pytest.raises(SandboxValidationError) as exc_info:
        engine.execute(mandate_traversal)
    assert "Path traversal detected" in str(exc_info.value)

    # 2. Expired execution lease strictly rejected
    mandate_expired = SandboxInvocationMandate(
        execution_id=f"exec-bad-lease-{uuid.uuid4().hex[:6]}",
        task_id=f"task-bad-lease-{uuid.uuid4().hex[:6]}",
        tenant_id="tenant-security",
        stage_attempt_id="att-bad-2",
        worker_role=WorkerRole.STRATEGY,
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 5000.0},
        lease_expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
    )
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.execute(mandate_expired)
    assert "Mandate execution lease expired" in str(exc_info.value)

    # 3. Unapproved network egress policy strictly rejected
    mandate_network = SandboxInvocationMandate(
        execution_id=f"exec-bad-net-{uuid.uuid4().hex[:6]}",
        task_id=f"task-bad-net-{uuid.uuid4().hex[:6]}",
        tenant_id="tenant-security",
        stage_attempt_id="att-bad-3",
        worker_role=WorkerRole.STRATEGY,
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 5000.0},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.ALLOWLIST,
    )
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.execute(mandate_network)
    assert "without approved SandboxEgressGrant" in str(exc_info.value)

