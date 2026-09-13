"""Comprehensive verification suite for Milestone 5 (M5) Acceptance Checkpoint.

M5 verifies the completed evidence and approval chain:
T22 (Consolidated Evidence) -> T23 (Structured Action Previews) -> T24 (Cryptographic HITL Clearance) -> M5 COMPLETE
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewDossier,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    compute_preview_hash,
)
from app.schemas.agent_contracts import (
    AdCopyVariant,
    ChannelAllocation,
    CodeDiffEntry,
    ConfidenceInterval,
    ConsolidatedEvidencePackage,
    ContentScheduleItem,
    CreativePackage,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    UITemplateDefinition,
    VisualBrief,
)
from app.schemas.governance import RiskLevel, WorkerRole
from app.schemas.task_state import (
    CanonicalTaskState,
    MilestoneCheckpoint,
    MilestoneStatus,
    TaskDependency,
    TaskStatus,
)
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository
from tests.unit.test_action_preview_verification import _build_test_consolidated_package


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task {task_id} not found")
        return self.states[task_id]


def _make_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


def _setup_fully_approved_m5_chain(
    tenant_id: str = "tenant-alpha",
) -> tuple[
    TaskStateService,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    ConsolidatedEvidencePackage,
    ActionPreviewDossier,
    HitlCoordinator,
]:
    repo: Any = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    service = TaskStateService(repo, provenance_recorder=prov_recorder)

    t22_task = CanonicalTaskState(task_id="task-t22", directive_id="dir-1", worker_role=WorkerRole.STRATEGY, status=TaskStatus.COMPLETED)
    t23_task = CanonicalTaskState(task_id="task-t23", directive_id="dir-1", worker_role=WorkerRole.STRATEGY, status=TaskStatus.COMPLETED)
    t24_task = CanonicalTaskState(task_id="task-t24", directive_id="dir-1", worker_role=WorkerRole.STRATEGY, status=TaskStatus.APPROVED)

    repo.states[t22_task.task_id] = t22_task
    repo.states[t23_task.task_id] = t23_task
    repo.states[t24_task.task_id] = t24_task

    package = _build_test_consolidated_package(tenant_id)
    generator = HitlPreviewGenerator()
    dossier = generator.generate_dossier(package)

    priv_key, pub_pem = _make_keypair()
    val = CryptographicValidator(pub_pem)
    coordinator = HitlCoordinator(val)

    # Approve all previews with valid cryptographic signatures and authorized roles
    role_map = {
        ActionPreviewKind.SPEND: (ReviewerRole.FINANCE, "[email protected]"),
        ActionPreviewKind.CLAIM: (ReviewerRole.LEGAL, "[email protected]"),
        ActionPreviewKind.COPY: (ReviewerRole.BRAND_LEAD, "[email protected]"),
        ActionPreviewKind.CODE_DIFF: (ReviewerRole.ENGINEERING, "[email protected]"),
    }

    now_dt = datetime.now(UTC)
    for preview in dossier.previews:
        coordinator.submit_for_approval(preview)
        role, approver = role_map.get(preview.kind, (ReviewerRole.ADMIN, "[email protected]"))
        content_hash = compute_preview_hash(preview)
        canon_bytes = canonical_decision_bytes(
            preview_id=preview.preview_id,
            decision="APPROVE",
            approver=approver,
            tenant_id=tenant_id,
            preview_content_hash=content_hash,
            decided_at=now_dt.isoformat(),
        )
        sig = sign_payload(canon_bytes, priv_key)
        coordinator.decide(
            preview.preview_id,
            decision=HumanDecisionType.APPROVE,
            approver=approver,
            approver_role=role,
            tenant_id=tenant_id,
            signature=sig,
            public_key_pem=pub_pem,
            preview_content_hash=content_hash,
            decided_at=now_dt,
        )

    return service, t22_task, t23_task, t24_task, package, dossier, coordinator


@pytest.mark.asyncio
async def test_m5_complete_when_all_accepted_and_cryptographically_cleared() -> None:
    """M5 evaluates to COMPLETE when T22, T23, and T24 are accepted and cryptographic clearances are verified."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.milestone_id == "M5"
    assert checkpoint.status == MilestoneStatus.COMPLETE
    assert len(checkpoint.blockers) == 0
    assert len(checkpoint.clearance_ids) == len(dossier.previews)

    # Persisted in CTS state
    saved_t24 = await service.get_state(t24.task_id)
    assert "milestone_m5" in saved_t24.cts_state
    assert saved_t24.cts_state["milestone_m5"]["status"] == "complete"


@pytest.mark.asyncio
async def test_m5_partial_when_t22_or_t23_incomplete() -> None:
    """M5 evaluates to PARTIAL when an upstream task is still in progress."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    t22_in_progress = t22.model_copy(update={"status": TaskStatus.IN_PROGRESS})

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22_in_progress,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.PARTIAL
    assert any("T22 is not COMPLETED" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_when_t24_rejected_or_revision_requested() -> None:
    """M5 evaluates to BLOCKED when human reviewer rejects or requests revision."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    
    # Mark one preview as REVISION_REQUESTED
    target_preview = dossier.previews[0]
    coordinator._pending[target_preview.preview_id] = target_preview
    coordinator.decide(
        target_preview.preview_id,
        decision=HumanDecisionType.REQUEST_REVISION,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id="tenant-alpha",
        revision_notes="Needs updated budget contingency",
    )

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("revision requested" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_on_invalid_or_forged_signature() -> None:
    """M5 fails closed when a preview has an invalid cryptographic signature."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    
    # Tamper with the clearance signature
    target_preview = dossier.previews[0]
    decision = coordinator.get_decision(target_preview.preview_id)
    assert decision is not None and decision.clearance is not None
    decision.clearance.signature = "invalid_forged_signature_bytes"

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("Cryptographic signature verification failed" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_on_replayed_signature_across_previews() -> None:
    """M5 fails closed if a signature from preview A is replayed on preview B."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    
    dec_a = coordinator.get_decision(dossier.previews[0].preview_id)
    dec_b = coordinator.get_decision(dossier.previews[1].preview_id)
    assert dec_a is not None and dec_b is not None
    assert dec_a.clearance is not None and dec_b.clearance is not None

    # Replay signature from A onto B
    dec_b.clearance.signature = dec_a.clearance.signature

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("signature verification failed" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_on_mutated_preview_artifact() -> None:
    """M5 fails closed if preview content is mutated after signed clearance was issued."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    
    # Mutate preview content after clearance
    dossier.previews[0].summary = "MUTATED CONTENT AFTER APPROVAL"

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("Preview content hash mismatch" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_on_cross_tenant_clearance() -> None:
    """M5 fails closed if evaluated tenant differs from clearance tenant."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain("tenant-alpha")

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-beta",  # mismatch!
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("tenant mismatch" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_blocked_when_task_hold_or_lock_present() -> None:
    """M5 evaluates to BLOCKED when a task hold or prerequisite lock is present."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()
    t24_held = t24.model_copy(update={"status": TaskStatus.HELD, "hold_reason": "Auditing legal compliance"})

    checkpoint = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24_held,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("T24 is HELD" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m5_evaluation_deterministic_and_idempotent() -> None:
    """Multiple evaluations of identical state produce identical milestone checkpoints."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()

    cp1 = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    cp2 = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert cp1.status == cp2.status == MilestoneStatus.COMPLETE
    assert cp1.clearance_ids == cp2.clearance_ids
    assert cp1.blockers == cp2.blockers == []


@pytest.mark.asyncio
async def test_m5_invalidated_when_linked_task_reopened() -> None:
    """Transitioning an approved task back to HELD/IN_PROGRESS invalidates M5 completion."""
    service, t22, t23, t24, package, dossier, coordinator = _setup_fully_approved_m5_chain()

    initial = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )
    assert initial.status == MilestoneStatus.COMPLETE

    # Reopen T24 to HELD
    t24_reopened = t24.model_copy(update={"status": TaskStatus.HELD, "hold_reason": "Quality re-check"})

    reopened_cp = await service.evaluate_m5_checkpoint(
        tenant_id="tenant-alpha",
        t22_task=t22,
        t23_task=t23,
        t24_task=t24_reopened,
        evidence_package=package,
        dossier=dossier,
        hitl_coordinator=coordinator,
    )

    assert reopened_cp.status == MilestoneStatus.BLOCKED
    assert any("T24 is HELD" in b for b in reopened_cp.blockers)


def test_m5_does_not_create_duplicate_outbound_gate_for_t25() -> None:
    """T25 execution eligibility is governed strictly by canonical DAG dependency on T24."""
    scheduler = DagScheduler()

    t24 = CanonicalTaskState(
        task_id="task-t24",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.AWAITING_APPROVAL,
    )
    t25 = CanonicalTaskState(
        task_id="task-t25",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-t24", downstream_task_id="task-t25")],
    )

    # When T24 is AWAITING_APPROVAL, T25 is not ready
    ready = scheduler.next_ready_tasks([t24, t25])
    assert t25 not in ready

    # When T24 is COMPLETED/APPROVED, T25 becomes ready
    t24_completed = t24.model_copy(update={"status": TaskStatus.COMPLETED})
    ready_after = scheduler.next_ready_tasks([t24_completed, t25])
    assert t25 in ready_after
