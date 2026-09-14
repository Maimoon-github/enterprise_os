"""Unit and Integration Tests for Task-34 (T34) / Milestone 7 (M7): Final Verification & Project Closeout.

Validates:
1. Authoritative dependencies: T32 (Institutional Memory promotion) and T33 (W3C PROV audit lineage).
2. Model A boundary: no worker or specialist agent executes project closeout.
3. Full 7-worker sandbox coverage: W_DEV->S_CODE, W_STRAT->S_ALLOC, W_CREAT->S_COPY, W_PROD->S_VAL, W_COMP->S_SCRAPE, W_VOICE->S_PARSE, W_LEARN->S_ATTR.
4. Ephemeral working state isolation: scratchpad and session state remain non-authoritative.
5. Explicit Brand Stakeholder / Portfolio Owner sign-off mandate (auto-signing strictly forbidden).
6. Immutable audit event emission for milestone M7 checkpoint.
7. CTS task-t34 completion and project closure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import pytest

from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.capabilities import CAPABILITY_REGISTRY
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import (
    CanonicalTaskState,
    MilestoneCheckpoint,
    MilestoneStatus,
    ProjectCloseoutDossier,
    StakeholderSignOff,
    TaskStatus,
)
from app.security.authorization_boundary import CallerIdentity
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _setup_t34_environment(
    tenant_id: str = "tenant-alpha",
    t32_status: TaskStatus = TaskStatus.COMPLETED,
    t32_ready: bool = True,
    has_t32: bool = True,
    t33_status: TaskStatus = TaskStatus.COMPLETED,
    t33_ready: bool = True,
    t33_valid: bool = True,
    has_t33: bool = True,
) -> tuple[
    TaskStateService,
    FakeProvenanceRepository,
    dict[str, CanonicalTaskState],
    CallerIdentity,
]:
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_repo = _FakeTaskStateRepository()
    task_service = TaskStateService(task_repo, provenance_recorder=prov_recorder)

    task_states: dict[str, CanonicalTaskState] = {}

    # Upstream T30 & T31
    t30 = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t30"] = t30
    task_repo.states["task-t30"] = t30

    t31 = CanonicalTaskState(
        task_id="task-t31",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t31"] = t31
    task_repo.states["task-t31"] = t31

    # T32 Dependency
    if has_t32:
        t32 = CanonicalTaskState(
            task_id="task-t32",
            directive_id="dir-1",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t32_status,
            governance_approved=True,
            cts_state={
                "tenant_id": tenant_id,
                "promoted_memory_id": "mem-t32-001",
                "t34_ready": t32_ready,
            },
        )
        task_states["task-t32"] = t32
        task_repo.states["task-t32"] = t32

    # T33 Dependency
    if has_t33:
        t33 = CanonicalTaskState(
            task_id="task-t33",
            directive_id="dir-1",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t33_status,
            governance_approved=True,
            cts_state={
                "tenant_id": tenant_id,
                "is_valid": t33_valid,
                "t34_ready": t33_ready,
                "audit_validation_id": "val-t33-001",
            },
        )
        task_states["task-t33"] = t33
        task_repo.states["task-t33"] = t33

    # T34 Task
    t34 = CanonicalTaskState(
        task_id="task-t34",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t34"] = t34
    task_repo.states["task-t34"] = t34

    ie_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id=tenant_id),
        risk_ceiling=RiskLevel.HIGH,
    )

    return task_service, prov_repo, task_states, ie_caller


def _valid_stakeholder_signoff() -> StakeholderSignOff:
    return StakeholderSignOff(
        stakeholder_id="stakeholder-brand-owner-001",
        stakeholder_role="Brand Stakeholder / Portfolio Owner",
        decision="APPROVED",
        signature="ed25519-valid-stakeholder-signature",
        notes="Final acceptance criteria fully satisfied across all omnichannel and learning surfaces.",
    )


# ============================================================================
# 1. Authoritative Dependencies (T32, T33)
# ============================================================================

@pytest.mark.asyncio
async def test_t34_fails_closed_when_t32_missing() -> None:
    """T34 closeout fails closed if T32 (Institutional Memory promotion) is absent."""
    service, _, task_states, caller = _setup_t34_environment(has_t32=False)
    signoff = _valid_stakeholder_signoff()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states.get("task-t32"),
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.PARTIAL
    assert dossier.project_status == "NOT_CLOSED"
    assert any("T32 memory promotion task state missing" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_t34_fails_closed_when_t32_incomplete_or_unready() -> None:
    """T34 closeout is blocked if T32 is not completed or t34_ready is False."""
    service, _, task_states, caller = _setup_t34_environment(t32_ready=False)
    task_states["task-t32"].cts_state["promoted_memory_id"] = None
    signoff = _valid_stakeholder_signoff()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert dossier.project_status == "BLOCKED"
    assert any("T32 memory promotion has not confirmed t34_ready" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_t34_fails_closed_when_t33_missing() -> None:
    """T34 closeout fails closed if T33 (W3C PROV audit verification) is absent."""
    service, _, task_states, caller = _setup_t34_environment(has_t33=False)
    signoff = _valid_stakeholder_signoff()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states.get("task-t33"),
        t34_task=task_states["task-t34"],
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.PARTIAL
    assert dossier.project_status == "NOT_CLOSED"
    assert any("T33 audit lineage task state missing" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_t34_fails_closed_when_t33_invalid() -> None:
    """T34 closeout is blocked if T33 audit lineage verification reported is_valid=False."""
    service, _, task_states, caller = _setup_t34_environment(t33_valid=False)
    signoff = _valid_stakeholder_signoff()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert dossier.project_status == "BLOCKED"
    assert any("T33 audit lineage verification has not passed" in b for b in checkpoint.blockers)


# ============================================================================
# 2. Model A Separation & Caller Authority
# ============================================================================

@pytest.mark.asyncio
async def test_t34_rejects_worker_caller() -> None:
    """Worker or specialist calling T34 closeout directly raises PolicyViolationError."""
    service, _, task_states, _ = _setup_t34_environment()
    signoff = _valid_stakeholder_signoff()

    worker_caller = CallerIdentity(
        subject="W_LEARN",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker execution of T34.*forbidden"):
        await service.evaluate_m7_checkpoint(
            "tenant-alpha",
            t30_task=task_states["task-t30"],
            t31_task=task_states["task-t31"],
            t32_task=task_states["task-t32"],
            t33_task=task_states["task-t33"],
            t34_task=task_states["task-t34"],
            stakeholder_approval=signoff,
            caller=worker_caller,
        )


@pytest.mark.asyncio
async def test_t34_enforces_tenant_scope() -> None:
    """Caller with tenant scope mismatched from closeout tenant raises ValueError."""
    service, _, task_states, _ = _setup_t34_environment()
    signoff = _valid_stakeholder_signoff()

    mismatched_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-other"),
        risk_ceiling=RiskLevel.HIGH,
    )

    with pytest.raises(ValueError, match="Caller tenant scope.*does not match"):
        await service.evaluate_m7_checkpoint(
            "tenant-alpha",
            t30_task=task_states["task-t30"],
            t31_task=task_states["task-t31"],
            t32_task=task_states["task-t32"],
            t33_task=task_states["task-t33"],
            t34_task=task_states["task-t34"],
            stakeholder_approval=signoff,
            caller=mismatched_caller,
        )


# ============================================================================
# 3. Explicit Stakeholder Approval Mandate
# ============================================================================

@pytest.mark.asyncio
async def test_t34_blocked_without_explicit_stakeholder_sign_off() -> None:
    """T34 is blocked when stakeholder_approval is None (auto-signing strictly forbidden)."""
    service, _, task_states, caller = _setup_t34_environment()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=None,  # No approval provided!
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert dossier.project_status == "BLOCKED"
    assert dossier.stakeholder_approved is False
    assert any("Explicit Brand Stakeholder / Portfolio Owner sign-off is required" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_t34_blocked_on_unauthorized_stakeholder_role() -> None:
    """Sign-off by an unauthorized role (e.g. Lead Developer instead of Brand Owner) is rejected."""
    service, _, task_states, caller = _setup_t34_environment()
    invalid_role_signoff = StakeholderSignOff(
        stakeholder_id="dev-001",
        stakeholder_role="Lead Developer",
        decision="APPROVED",
    )

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=invalid_role_signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert dossier.project_status == "BLOCKED"
    assert dossier.stakeholder_approved is False
    assert any("Sign-off role 'Lead Developer' is unauthorized" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_t34_blocked_on_rejected_stakeholder_decision() -> None:
    """Explicit rejection by Brand Stakeholder blocks project closeout."""
    service, _, task_states, caller = _setup_t34_environment()
    rejected_signoff = StakeholderSignOff(
        stakeholder_id="owner-001",
        stakeholder_role="Brand Stakeholder / Portfolio Owner",
        decision="REJECTED",
        notes="Conversion rate targets in Meta campaigns were not met.",
    )

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
        stakeholder_approval=rejected_signoff,
        caller=caller,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert dossier.project_status == "BLOCKED"
    assert dossier.stakeholder_approved is False
    assert any("Brand Stakeholder rejected project closeout" in b for b in checkpoint.blockers)


# ============================================================================
# 4. Sandbox Coverage & Model A Invariant Verification
# ============================================================================

def test_t34_verifies_all_seven_sandbox_mappings() -> None:
    """Verifies that all 7 workers map to their respective specialist micro-tools in the registry."""
    mappings = {
        WorkerRole.DEVELOPMENT: SandboxCapability.CODE,
        WorkerRole.STRATEGY: SandboxCapability.ALLOC,
        WorkerRole.CREATIVE_CONTENT: SandboxCapability.COPY,
        WorkerRole.PRODUCT_EVIDENCE: SandboxCapability.VAL,
        WorkerRole.COMPETITOR_INTEL: SandboxCapability.SCRAPE,
        WorkerRole.CUSTOMER_VOICE: SandboxCapability.PARSE,
        WorkerRole.LEARNING_PERFORMANCE: SandboxCapability.ATTR,
    }

    for worker, cap in mappings.items():
        profile = CAPABILITY_REGISTRY.get(cap)
        assert profile is not None, f"Missing capability profile for {cap}"
        assert profile.allowed_worker == worker, f"Capability {cap} not mapped to {worker}"


# ============================================================================
# 5. Successful Project Closeout (T34 Acceptance & M7 COMPLETE)
# ============================================================================

@pytest.mark.asyncio
async def test_t34_successful_project_closeout() -> None:
    """All dependencies valid, Model A verified, Stakeholder approves -> M7 COMPLETE & Project CLOSED."""
    service, prov_repo, task_states, caller = _setup_t34_environment()
    signoff = _valid_stakeholder_signoff()

    checkpoint, dossier = await service.evaluate_m7_checkpoint(
        "tenant-alpha",
        t30_task=task_states["task-t30"],
        t31_task=task_states["task-t31"],
        t32_task=task_states["task-t32"],
        t33_task=task_states["task-t33"],
        t34_task=task_states["task-t34"],
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
    assert dossier.model_a_verified is True
    assert dossier.sandbox_coverage_verified is True
    assert dossier.ephemeral_boundaries_verified is True
    assert dossier.closed_at is not None

    # 3. CTS task-t34 state verification
    t34_saved = task_states["task-t34"]
    assert t34_saved.status == TaskStatus.COMPLETED
    assert "milestone_m7" in t34_saved.cts_state
    assert t34_saved.cts_state["milestone_m7"]["status"] == "complete"
    assert "project_closeout" in t34_saved.cts_state
    assert t34_saved.cts_state["project_closeout"]["project_status"] == "CLOSED"

    # 4. Provenance audit event verification
    chain = prov_repo._chains["tenant-alpha"]
    m7_events = [r for r in chain if r.activity == "milestone_checkpoint_m7"]
    assert len(m7_events) == 1
    assert m7_events[0].metadata["status"] == "complete"
    assert m7_events[0].metadata["project_status"] == "CLOSED"
    assert m7_events[0].metadata["stakeholder_approved"] is True
