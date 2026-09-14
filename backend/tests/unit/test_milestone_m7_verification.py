"""Comprehensive verification suite for Milestone 7 (M7) Acceptance Checkpoint.

M7 aggregates and verifies the final closed-loop telemetry optimization and project closeout:
T30 (Telemetry Persisted) + T31 (Attribution/Decay) + T32 (Memory Promotion) + T33 (Audit Lineage & Integrity) + T34 (Final Verification & Closeout) -> M7 COMPLETE -> Project CLOSED.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import pytest

from app.core.exceptions import PolicyViolationError
from app.orchestration.dag_scheduler import DagScheduler
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.security.authorization_boundary import CallerIdentity
from app.schemas.task_state import (
    CanonicalTaskState,
    MilestoneCheckpoint,
    MilestoneStatus,
    ProjectCloseoutDossier,
    StakeholderSignOff,
    TaskDependency,
    TaskStatus,
)
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task {task_id} not found")
        return self.states[task_id]


def _build_valid_m7_fixtures(
    tenant_id: str = "tenant-alpha",
) -> tuple[
    TaskStateService,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    StakeholderSignOff,
    FakeProvenanceRepository,
    CallerIdentity,
]:
    repo = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    service = TaskStateService(repo, provenance_recorder=prov_recorder)

    # T30: Live telemetry persisted in CDB
    t30 = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={
            "tenant_id": tenant_id,
            "telemetry_stored": True,
            "events_persisted": 50,
        },
        governance_approved=True,
    )

    # T31: Multi-touch attribution, creative decay & ROAS calculated
    t31 = CanonicalTaskState(
        task_id="task-t31",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={
            "tenant_id": tenant_id,
            "learning_evidence_valid": True,
            "attribution_calculated": True,
        },
        governance_approved=True,
    )

    # T32: Approved learning deltas promoted into MEM
    t32 = CanonicalTaskState(
        task_id="task-t32",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={
            "tenant_id": tenant_id,
            "memory_promoted": True,
            "promoted_memory_id": "mem-t32-delta-001",
            "t34_ready": True,
        },
        governance_approved=True,
    )

    # T33: W3C PROV audit lineage, cryptographic hash chain, Ed25519 signatures
    t33 = CanonicalTaskState(
        task_id="task-t33",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={
            "tenant_id": tenant_id,
            "is_valid": True,
            "t34_ready": True,
            "audit_validation_id": "val-t33-001",
        },
        governance_approved=True,
    )

    # T34: Final architecture verification & closeout
    closeout_dossier = ProjectCloseoutDossier(
        closeout_id="closeout-t34-001",
        tenant_id=tenant_id,
        milestone_m7_status=MilestoneStatus.COMPLETE,
        project_status="CLOSED",
        t32_learning_status="completed",
        t33_audit_status="completed",
        model_a_verified=True,
        sandbox_coverage_verified=True,
        governance_verified=True,
        ephemeral_boundaries_verified=True,
        stakeholder_approved=True,
        closed_at=datetime.now(UTC),
    )

    t34 = CanonicalTaskState(
        task_id="task-t34",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={
            "tenant_id": tenant_id,
            "project_closeout": closeout_dossier.model_dump(mode="json"),
        },
        governance_approved=True,
    )

    signoff = StakeholderSignOff(
        stakeholder_id="stakeholder-brand-1",
        stakeholder_role="Brand Stakeholder / Portfolio Owner",
        decision="APPROVED",
        notes="Final project closeout approved.",
    )

    repo.states[t30.task_id] = t30
    repo.states[t31.task_id] = t31
    repo.states[t32.task_id] = t32
    repo.states[t33.task_id] = t33
    repo.states[t34.task_id] = t34

    caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id=tenant_id),
        risk_ceiling=RiskLevel.HIGH,
    )

    return service, t30, t31, t32, t33, t34, signoff, prov_repo, caller


@pytest.mark.asyncio
async def test_m7_checkpoint_full_success() -> None:
    """M7 evaluates to COMPLETE and project to CLOSED when all T30-T34 tasks are valid."""
    service, t30, t31, t32, t33, t34, signoff, prov_repo, caller = _build_valid_m7_fixtures()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )

    # 1. Milestone Checkpoint Verification
    assert isinstance(checkpoint, MilestoneCheckpoint)
    assert checkpoint.milestone_id == "M7"
    assert checkpoint.status == MilestoneStatus.COMPLETE
    assert len(checkpoint.blockers) == 0

    # 2. Project Closeout Dossier Verification
    assert isinstance(dossier, ProjectCloseoutDossier)
    assert dossier.project_status == "CLOSED"
    assert dossier.milestone_m7_status == MilestoneStatus.COMPLETE
    assert dossier.stakeholder_approved is True
    assert dossier.closed_at is not None

    # 3. Provenance Event Verification
    chain = prov_repo._chains["tenant-alpha"]
    m7_events = [r for r in chain if r.activity == "milestone_checkpoint_m7"]
    assert len(m7_events) == 1
    assert m7_events[0].metadata["status"] == "complete"
    assert m7_events[0].metadata["project_status"] == "CLOSED"
    assert m7_events[0].metadata["stakeholder_approved"] is True


@pytest.mark.asyncio
async def test_m7_fails_closed_when_tasks_missing() -> None:
    """M7 fails closed to PARTIAL when any linked task is missing or uninitialized."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # Missing T30
    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=None,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.PARTIAL
    assert dos.project_status == "NOT_CLOSED"
    assert any("T30 telemetry ingestion task state missing" in b for b in cp.blockers)

    # Missing T34
    cp2, dos2 = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=None,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp2.status == MilestoneStatus.PARTIAL
    assert dos2.project_status == "NOT_CLOSED"
    assert any("T34 project closeout task state missing" in b for b in cp2.blockers)


@pytest.mark.asyncio
async def test_m7_fails_when_any_task_failed_or_rejected() -> None:
    """M7 fails closed to FAILED when any linked task is FAILED or REJECTED."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # T31 FAILED
    t31_failed = t31.model_copy(update={"status": TaskStatus.FAILED, "failure_reason": "Attribution sandbox crash"})
    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31_failed,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.FAILED
    assert dos.project_status == "FAILED"
    assert any("T31 is in failed state 'failed'" in b for b in cp.blockers)

    # T33 REJECTED
    t33_rejected = t33.model_copy(update={"status": TaskStatus.REJECTED})
    cp2, dos2 = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33_rejected,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp2.status == MilestoneStatus.FAILED
    assert dos2.project_status == "FAILED"
    assert any("T33 is in failed state 'rejected'" in b for b in cp2.blockers)


@pytest.mark.asyncio
async def test_m7_invalidated_when_linked_task_reopened() -> None:
    """Transitioning an approved task back to HELD or setting is_reopened invalidates M7 to BLOCKED."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # Initial evaluation is COMPLETE
    init_cp, _ = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert init_cp.status == MilestoneStatus.COMPLETE

    # Reopen T30 for telemetry re-ingestion
    t30_reopened = t30.model_copy(update={"status": TaskStatus.HELD, "hold_reason": "Emergency telemetry replay"})
    reopened_cp, reopened_dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30_reopened,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert reopened_cp.status == MilestoneStatus.BLOCKED
    assert reopened_dos.project_status == "BLOCKED"
    assert any("T30 is HELD" in b for b in reopened_cp.blockers)


@pytest.mark.asyncio
async def test_m7_invalidated_when_linked_task_rolled_back_or_revoked() -> None:
    """A task marked as rolled_back, revoked, or invalidated invalidates M7 to BLOCKED."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # T32 rolled back
    t32_rb_state = dict(t32.cts_state)
    t32_rb_state["rolled_back"] = True
    t32_rb = t32.model_copy(update={"cts_state": t32_rb_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32_rb,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert dos.project_status == "BLOCKED"
    assert any("T32 is HELD or has active locks/reopen/rollback" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_governance_approval() -> None:
    """M7 blocks if any task lacks governance approval."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t31_unapproved = t31.model_copy(update={"governance_approved": False})
    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31_unapproved,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert dos.project_status == "BLOCKED"
    assert any("T31 governance approval is unresolved" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_enforces_tenant_isolation_across_tasks() -> None:
    """M7 blocks if any linked task belongs to a different tenant."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t33_rogue = t33.model_copy(update={"cts_state": {"tenant_id": "tenant-beta", "is_valid": True, "t34_ready": True}})
    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33_rogue,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert dos.project_status == "BLOCKED"
    assert any("T33 tenant mismatch (tenant-beta != tenant-alpha)" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_valid_t30_telemetry_persisted() -> None:
    """M7 blocks if T30 reports telemetry not durably persisted or missing evidence."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t30_bad_state = dict(t30.cts_state)
    t30_bad_state["telemetry_stored"] = False
    t30_bad = t30.model_copy(update={"cts_state": t30_bad_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30_bad,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert any("T30 live telemetry is not durably persisted" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_valid_t31_learning_evidence() -> None:
    """M7 blocks if T31 reports invalid learning evidence."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t31_bad_state = dict(t31.cts_state)
    t31_bad_state["learning_evidence_valid"] = False
    t31_bad = t31.model_copy(update={"cts_state": t31_bad_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31_bad,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert any("T31 learning evidence or attribution calculation is invalid" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_valid_t32_memory_promotion() -> None:
    """M7 blocks if T32 memory promotion is unready or revoked."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # Promotion revoked
    t32_revoked_state = dict(t32.cts_state)
    t32_revoked_state["promotion_revoked"] = True
    t32_revoked = t32.model_copy(update={"cts_state": t32_revoked_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32_revoked,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert any("T32 memory promotion has been revoked or invalidated" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_valid_t33_audit_integrity() -> None:
    """M7 blocks if T33 reports invalid audit integrity or broken hash chain."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t33_broken_state = dict(t33.cts_state)
    t33_broken_state["chain_broken"] = True
    t33_broken = t33.model_copy(update={"cts_state": t33_broken_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33_broken,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert any("T33 audit integrity has been invalidated" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_requires_t34_project_closed() -> None:
    """M7 blocks if T34 closeout dossier indicates project was NOT_CLOSED or BLOCKED."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    t34_not_closed_state = dict(t34.cts_state)
    dossier_data = dict(t34_not_closed_state["project_closeout"])
    dossier_data["project_status"] = "NOT_CLOSED"
    t34_not_closed_state["project_closeout"] = dossier_data
    t34_not_closed = t34.model_copy(update={"cts_state": t34_not_closed_state})

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34_not_closed,
        stakeholder_approval=signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert dos.project_status == "BLOCKED"
    assert any("T34 project closeout dossier indicates project is not CLOSED" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_blocks_when_stakeholder_rejected_or_unauthorized() -> None:
    """M7 blocks if stakeholder rejects closeout or has unauthorized role."""
    service, t30, t31, t32, t33, t34, _, _, caller = _build_valid_m7_fixtures()

    # Rejected sign-off
    rej_signoff = StakeholderSignOff(
        stakeholder_id="stk-1",
        stakeholder_role="Brand Stakeholder",
        decision="REJECTED",
        notes="Audit gaps remain.",
    )
    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=rej_signoff,
        caller=caller,
    )
    assert cp.status == MilestoneStatus.BLOCKED
    assert dos.project_status == "BLOCKED"
    assert any("Brand Stakeholder rejected project closeout" in b for b in cp.blockers)


@pytest.mark.asyncio
async def test_m7_deterministic_and_idempotent() -> None:
    """Evaluating M7 multiple times yields identical outcomes without state drift."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    cp1, dos1 = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )

    cp2, dos2 = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert cp1.status == cp2.status == MilestoneStatus.COMPLETE
    assert dos1.project_status == dos2.project_status == "CLOSED"
    assert cp1.blockers == cp2.blockers == []


def test_m7_preserves_canonical_dag() -> None:
    """M7 does not alter the canonical DAG dependency structure:
    T29 -> T30 -> T31 -> T32, T30 + T31 -> T33, T32 + T33 -> T34.
    """
    scheduler = DagScheduler()

    t29 = CanonicalTaskState(task_id="task-t29", directive_id="dir-1", worker_role=WorkerRole.LEARNING_PERFORMANCE, status=TaskStatus.COMPLETED)
    t30 = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-t29", downstream_task_id="task-t30")],
    )
    t31 = CanonicalTaskState(
        task_id="task-t31",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-t30", downstream_task_id="task-t31")],
    )
    t32 = CanonicalTaskState(
        task_id="task-t32",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-t31", downstream_task_id="task-t32")],
    )
    t33 = CanonicalTaskState(
        task_id="task-t33",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[
            TaskDependency(upstream_task_id="task-t30", downstream_task_id="task-t33"),
            TaskDependency(upstream_task_id="task-t31", downstream_task_id="task-t33"),
        ],
    )
    t34 = CanonicalTaskState(
        task_id="task-t34",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[
            TaskDependency(upstream_task_id="task-t32", downstream_task_id="task-t34"),
            TaskDependency(upstream_task_id="task-t33", downstream_task_id="task-t34"),
        ],
    )

    tasks = [t29, t30, t31, t32, t33, t34]

    # Initially, with only T29 completed, only T30 is ready
    ready = scheduler.next_ready_tasks(tasks)
    assert len(ready) == 1
    assert ready[0].task_id == "task-t30"

    # When T30 completes, T31 is ready (and T33 still awaits T31)
    t30.status = TaskStatus.COMPLETED
    ready = scheduler.next_ready_tasks(tasks)
    assert len(ready) == 1
    assert ready[0].task_id == "task-t31"

    # When T31 completes, T32 and T33 become ready
    t31.status = TaskStatus.COMPLETED
    ready = scheduler.next_ready_tasks(tasks)
    ready_ids = {t.task_id for t in ready}
    assert ready_ids == {"task-t32", "task-t33"}

    # When T32 completes but T33 is pending, T34 is not ready
    t32.status = TaskStatus.COMPLETED
    ready = scheduler.next_ready_tasks(tasks)
    assert [t.task_id for t in ready] == ["task-t33"]

    # When both T32 and T33 complete, T34 becomes ready
    t33.status = TaskStatus.COMPLETED
    ready = scheduler.next_ready_tasks(tasks)
    assert [t.task_id for t in ready] == ["task-t34"]


@pytest.mark.asyncio
async def test_m7_model_a_blocks_worker_caller() -> None:
    """Model A blocks worker or specialist callers from invoking M7 checkpoint."""
    service, t30, t31, t32, t33, t34, signoff, _, _ = _build_valid_m7_fixtures()

    worker_caller = CallerIdentity(
        subject="W_LEARN",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker execution"):
        await service.evaluate_m7_checkpoint(
            tenant_id="tenant-alpha",
            t30_task=t30,
            t31_task=t31,
            t32_task=t32,
            t33_task=t33,
            t34_task=t34,
            stakeholder_approval=signoff,
            caller=worker_caller,
        )


@pytest.mark.asyncio
async def test_m7_zero_execution_of_linked_tasks() -> None:
    """M7 evaluates existing records without executing ingestion, attribution, promotion, or audit validator."""
    service, t30, t31, t32, t33, t34, signoff, _, caller = _build_valid_m7_fixtures()

    # Pre-record event counts and cts_state snapshots
    t30_state_before = dict(t30.cts_state)
    t31_state_before = dict(t31.cts_state)
    t32_state_before = dict(t32.cts_state)
    t33_state_before = dict(t33.cts_state)

    cp, dos = await service.evaluate_m7_checkpoint(
        tenant_id="tenant-alpha",
        t30_task=t30,
        t31_task=t31,
        t32_task=t32,
        t33_task=t33,
        t34_task=t34,
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert cp.status == MilestoneStatus.COMPLETE
    assert dos.project_status == "CLOSED"

    # CTS states of upstream tasks are unmodified
    assert t30.cts_state == t30_state_before
    assert t31.cts_state == t31_state_before
    assert t32.cts_state == t32_state_before
    assert t33.cts_state == t33_state_before
