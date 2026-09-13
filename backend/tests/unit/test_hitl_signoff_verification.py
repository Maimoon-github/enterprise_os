"""Comprehensive verification suite for T24 Human-in-the-Loop Sign-Off Gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from app.core.exceptions import (
    ApprovalRequiredError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
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
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import RiskLevel, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository


def _make_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


def _make_preview(
    kind: ActionPreviewKind = ActionPreviewKind.SPEND,
    preview_id: str = "prev-spend-1",
    task_id: str = "task-strat-1",
    tenant_id: str = "tenant-alpha",
    spend_amount: float | None = 25000.0,
    diff: str | None = None,
) -> ActionPreview:
    return ActionPreview(
        preview_id=preview_id,
        task_id=task_id,
        tenant_id=tenant_id,
        kind=kind,
        summary=f"Proposed {kind.value} action for task {task_id}",
        spend_amount=spend_amount,
        diff=diff,
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        review_status=ReviewStatus.PENDING,
    )


# =========================================================================
# Unit Tests
# =========================================================================

def test_approve_preview_with_valid_cryptographic_signature() -> None:
    """Valid human sign-off with Ed25519 signature and matching role unlocks approval."""
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    coordinator = HitlCoordinator(validator)

    preview = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-1", tenant_id="tenant-alpha")
    coordinator.submit_for_approval(preview)

    content_hash = compute_preview_hash(preview)
    now_dt = datetime.now(UTC)

    # Human reviewer signs canonical decision bytes
    canon_bytes = canonical_decision_bytes(
        preview_id="prev-1",
        decision="APPROVE",
        approver="[email protected]",
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        decided_at=now_dt.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    decision = coordinator.decide(
        "prev-1",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id="tenant-alpha",
        signature=sig,
        preview_content_hash=content_hash,
        decided_at=now_dt,
    )

    assert decision.approved is True
    assert decision.decision == HumanDecisionType.APPROVE
    assert decision.clearance is not None
    assert decision.clearance.is_valid is True
    assert preview.review_status == ReviewStatus.APPROVED

    # Clearance is verified
    approved = coordinator.require_approved("prev-1")
    assert approved.preview_id == "prev-1"


def test_reject_preview_blocks_dispatch() -> None:
    """Explicit REJECT decision marks preview as REJECTED and blocks require_approved."""
    coordinator = HitlCoordinator()
    preview = _make_preview(kind=ActionPreviewKind.CLAIM, preview_id="prev-claim-1")
    coordinator.submit_for_approval(preview)

    decision = coordinator.decide(
        "prev-claim-1",
        decision=HumanDecisionType.REJECT,
        approver="[email protected]",
        approver_role=ReviewerRole.LEGAL,
        revision_notes="Efficacy claim lacks double-blind clinical trial support.",
    )

    assert decision.approved is False
    assert decision.decision == HumanDecisionType.REJECT
    assert preview.review_status == ReviewStatus.REJECTED
    assert coordinator.is_approved("prev-claim-1") is False

    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        coordinator.require_approved("prev-claim-1")


def test_request_revision_keeps_execution_gated() -> None:
    """REQUEST_REVISION marks preview as REVISION_REQUESTED and blocks dispatch."""
    coordinator = HitlCoordinator()
    preview = _make_preview(kind=ActionPreviewKind.COPY, preview_id="prev-copy-1")
    coordinator.submit_for_approval(preview)

    decision = coordinator.decide(
        "prev-copy-1",
        decision=HumanDecisionType.REQUEST_REVISION,
        approver="[email protected]",
        approver_role=ReviewerRole.BRAND_LEAD,
        revision_notes="Tone of voice is overly informal; adjust headline for B2B tone.",
    )

    assert decision.approved is False
    assert decision.decision == HumanDecisionType.REQUEST_REVISION
    assert preview.review_status == ReviewStatus.REVISION_REQUESTED

    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        coordinator.require_approved("prev-copy-1")


def test_unauthorized_reviewer_role_fails_closed() -> None:
    """Reviewer with unauthorized domain role attempting sign-off raises PolicyViolationError."""
    coordinator = HitlCoordinator()
    preview = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-spend-unauth")
    coordinator.submit_for_approval(preview)

    # Engineering reviewer cannot sign off on SPEND
    with pytest.raises(PolicyViolationError, match="Reviewer role 'engineering' is not authorized to sign off on 'spend' previews"):
        coordinator.decide(
            "prev-spend-unauth",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.ENGINEERING,
        )


def test_cross_tenant_approval_rejected() -> None:
    """Reviewer tenant mismatch against preview tenant raises PolicyViolationError."""
    coordinator = HitlCoordinator()
    preview = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-tenant-1", tenant_id="tenant-alpha")
    coordinator.submit_for_approval(preview)

    # Reviewer from tenant-bravo attempting to sign off on tenant-alpha
    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        coordinator.decide(
            "prev-tenant-1",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.FINANCE,
            tenant_id="tenant-bravo",
        )


def test_tampered_preview_content_hash_fails_closed() -> None:
    """Modified preview content hash mismatching calculated content fails closed."""
    coordinator = HitlCoordinator()
    preview = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-tamper-1")
    coordinator.submit_for_approval(preview)

    fake_tampered_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(SignatureVerificationError, match="Preview content hash mismatch: preview has been tampered with or modified"):
        coordinator.decide(
            "prev-tamper-1",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.FINANCE,
            preview_content_hash=fake_tampered_hash,
        )


def test_invalid_or_forged_signature_fails_closed() -> None:
    """Forged or corrupted signature raises SignatureVerificationError."""
    _, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    coordinator = HitlCoordinator(validator)

    preview = _make_preview(kind=ActionPreviewKind.CODE_DIFF, preview_id="prev-diff-1", diff="+ change")
    coordinator.submit_for_approval(preview)

    content_hash = compute_preview_hash(preview)
    corrupted_sig = "aW52YWxpZF9zaWduYXR1cmVfZm9yZ2VkX2J5X2F0dGFja2VyCg=="

    with pytest.raises(SignatureVerificationError, match="Cryptographic signature verification failed"):
        coordinator.decide(
            "prev-diff-1",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.ENGINEERING,
            signature=corrupted_sig,
            preview_content_hash=content_hash,
        )


def test_replayed_signature_different_preview_rejected() -> None:
    """Signature generated for Preview A replayed on Preview B fails closed."""
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    coordinator = HitlCoordinator(validator)

    preview_a = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-A")
    preview_b = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-B")
    coordinator.submit_for_approval(preview_a)
    coordinator.submit_for_approval(preview_b)

    hash_a = compute_preview_hash(preview_a)
    now_dt = datetime.now(UTC)

    # Sign for preview A
    canon_bytes_a = canonical_decision_bytes(
        preview_id="prev-A",
        decision="APPROVE",
        approver="[email protected]",
        tenant_id="tenant-alpha",
        preview_content_hash=hash_a,
        decided_at=now_dt.isoformat(),
    )
    sig_a = sign_payload(canon_bytes_a, priv_key)

    # Replay sig_a on preview B
    hash_b = compute_preview_hash(preview_b)
    with pytest.raises(SignatureVerificationError, match="Cryptographic signature verification failed"):
        coordinator.decide(
            "prev-B",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.FINANCE,
            signature=sig_a,
            preview_content_hash=hash_b,
            decided_at=now_dt,
        )


def test_all_dossier_previews_must_be_approved_for_dossier_clearance() -> None:
    """Partial approval of a dossier fails is_dossier_approved."""
    coordinator = HitlCoordinator()
    prev_1 = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="p-1")
    prev_2 = _make_preview(kind=ActionPreviewKind.COPY, preview_id="p-2")

    dossier = ActionPreviewDossier(
        dossier_id="dossier-1",
        tenant_id="tenant-alpha",
        source_package_id="pkg-1",
        previews=[prev_1, prev_2],
        preview_count=2,
    )
    coordinator.submit_dossier(dossier)

    # Only approve p-1
    coordinator.decide("p-1", decision=HumanDecisionType.APPROVE, approver="[email protected]", approver_role=ReviewerRole.FINANCE)

    assert coordinator.is_approved("p-1") is True
    assert coordinator.is_approved("p-2") is False
    assert coordinator.is_dossier_approved(dossier) is False

    # Now approve p-2
    coordinator.decide("p-2", decision=HumanDecisionType.APPROVE, approver="[email protected]", approver_role=ReviewerRole.BRAND_LEAD)
    assert coordinator.is_dossier_approved(dossier) is True


def test_dispatch_before_approval_strictly_blocked() -> None:
    """HitlCoordinator blocks require_approved for unreviewed previews."""
    coordinator = HitlCoordinator()
    preview = _make_preview(preview_id="unreviewed-1")
    coordinator.submit_for_approval(preview)

    with pytest.raises(ApprovalRequiredError, match="has not been reviewed"):
        coordinator.require_approved("unreviewed-1")


@pytest.mark.asyncio
async def test_intelligence_engine_record_hitl_decision_flow() -> None:
    """IntelligenceEngine coordinates HITL decision, updates CTS task state, and records provenance."""
    fake_prov = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(fake_prov)
    coordinator = HitlCoordinator()
    state_machine = TaskStateMachine()

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=state_machine,
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=coordinator,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers={},
    )

    preview = _make_preview(kind=ActionPreviewKind.SPEND, preview_id="prev-cts-1", task_id="task-strat-1")
    coordinator.submit_for_approval(preview)

    task = CanonicalTaskState(
        task_id="task-strat-1",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.AWAITING_APPROVAL,
    )

    decision = await engine.record_hitl_decision(
        "prev-cts-1",
        decision="APPROVE",
        approver="[email protected]",
        approver_role="finance",
        tenant_id="tenant-alpha",
        task=task,
    )

    assert decision.approved is True
    assert decision.updated_task is not None
    assert decision.updated_task.status == TaskStatus.APPROVED

    # Provenance audit recorded
    records = fake_prov._chains.get("tenant-alpha", [])
    assert any(r.activity == "hitl_approve" for r in records)
    assert any(r.agent == "reviewer:[email protected]" for r in records)
