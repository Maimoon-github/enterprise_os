"""Focused unit and integration tests for Task DE-04: HITL Approval Gateway (W_DEV).

Validates:
1. Subagent completion requires mandatory HITL interruption (SUBAGENT_RUNNING -> RESULT_SEALED -> HITL_PENDING).
2. Review payload generation containing candidate diff, hashes, and machine policy status.
3. Reviewer authentication & role screening (engineering, admin, tech_lead, lead_engineer, brand_lead).
4. Cryptographic Ed25519 binding of approval tokens and tamper rejection.
5. Deterministic precedence: machine DENY + human APPROVE = DENY (fail-closed).
6. Tampered candidate/payload hash mismatch rejection by state machine guards.
7. Step and attempt mismatch rejection (no cross-step or cross-attempt token reuse).
8. Replay prevention for token IDs and nonces.
9. Token expiry enforcement.
10. Rejection and revision routing: HITL_PENDING -> CORRECTION_REQUIRED -> RETRY_PREPARED.
11. Restart-safe state persistence and recovery with approval tokens in CTS.
12. Transport API route POST /api/v1/approvals/development/decide.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fastapi.testclient import TestClient

from app.core.exceptions import InvalidTransitionError, PolicyViolationError
from app.main import create_app
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.orchestration.hitl_preview_generator import generate_development_review_payload
from app.schemas.action_preview import ActionPreviewKind
from app.schemas.development.approval_token import (
    DevelopmentApprovalToken,
    compute_output_snapshot_hash,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.task_state import (
    CanonicalTaskState,
    DevelopmentExecutionLease,
    DevelopmentWorkflowCheckpoint,
    DevelopmentWorkflowState,
    TaskStatus,
    WorkflowRetryPolicy,
)
from app.security.cryptographic_validator import CryptographicValidator
from app.services.hitl import HitlCoordinator
from app.services.task_state import TaskStateService


class FakeTaskStateRepository:
    """In-memory stand-in for task state repository."""

    def __init__(self) -> None:
        self._states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self._states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self._states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self._states[state.task_id] = state


@pytest.fixture
def state_machine() -> DevelopmentStateMachine:
    return DevelopmentStateMachine(
        retry_policy=WorkflowRetryPolicy(max_retries=3, retry_delay_seconds=0.1)
    )


@pytest.fixture
def hitl_coordinator() -> HitlCoordinator:
    return HitlCoordinator()


@pytest.fixture
def ed25519_key_pems(ed25519_keypair) -> tuple[str, str]:
    private_key, public_pem = ed25519_keypair
    private_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode("ascii")
    return private_pem, public_pem


@pytest.fixture
def active_lease() -> DevelopmentExecutionLease:
    return DevelopmentExecutionLease(
        workflow_id="wf-hitl-001",
        task_id="task-hitl-001",
        step_id="step-dev-impl",
        attempt_id="att-1",
        owner_id="worker-w-dev-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


# ===========================================================================
# 1. State Machine Mandatory HITL Interruption Tests
# ===========================================================================

def test_subagent_completion_requires_hitl(
    state_machine: DevelopmentStateMachine, active_lease: DevelopmentExecutionLease
) -> None:
    """Subagent must pass through RESULT_SEALED -> HITL_PENDING before APPROVED or NEXT_STEP."""
    task_id = "task-hitl-001"
    wf_id = "wf-hitl-001"

    # 1. SUBAGENT_RUNNING -> RESULT_SEALED
    cp_sealed = state_machine.transition(
        current_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
        target_state=DevelopmentWorkflowState.RESULT_SEALED,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-dev-impl",
        attempt_id="att-1",
        idempotency_key="seal-1",
        lease=active_lease,
        expected_owner="worker-w-dev-1",
    )
    assert cp_sealed.state == DevelopmentWorkflowState.RESULT_SEALED

    # 2. Cannot skip HITL_PENDING directly to APPROVED from RESULT_SEALED
    with pytest.raises(InvalidTransitionError):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.RESULT_SEALED,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id=task_id,
            workflow_id=wf_id,
            step_id="step-dev-impl",
            attempt_id="att-1",
            idempotency_key="illegal-approve",
        )

    # 3. Cannot transition to HITL_PENDING without candidate hash or deliverable
    with pytest.raises(PolicyViolationError, match="requires candidate_hash or deliverable"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.RESULT_SEALED,
            target_state=DevelopmentWorkflowState.HITL_PENDING,
            task_id=task_id,
            workflow_id=wf_id,
            step_id="step-dev-impl",
            attempt_id="att-1",
            idempotency_key="pending-no-data",
            state_data={},
        )

    # 4. Valid transition to HITL_PENDING with candidate_hash
    cp_pending = state_machine.transition(
        current_state=DevelopmentWorkflowState.RESULT_SEALED,
        target_state=DevelopmentWorkflowState.HITL_PENDING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-dev-impl",
        attempt_id="att-1",
        idempotency_key="pending-1",
        state_data={"candidate_hash": "sha256-output-candidate-abc"},
    )
    assert cp_pending.state == DevelopmentWorkflowState.HITL_PENDING


# ===========================================================================
# 2. Review Payload Generation
# ===========================================================================

def test_generate_review_payload() -> None:
    """Review payload contains diff, hashes, step identity, and machine policy status."""
    candidate_output = {
        "status": "success",
        "changed_files": ["app/core/engine.py"],
        "diff": "--- a/engine.py\n+++ b/engine.py\n@@ -1 +1 @@\n-old\n+new",
    }
    input_mandate = {
        "task_id": "task-hitl-002",
        "capability": "code_execution",
        "requirements": ["Implement engine update"],
    }

    payload = generate_development_review_payload(
        task_id="task-hitl-002",
        workflow_id="wf-hitl-002",
        step_id="step-2",
        attempt_id="att-1",
        subagent_id="subagent-code-1",
        candidate_output=candidate_output,
        input_mandate=input_mandate,
        machine_policy_allowed=True,
    )

    preview = payload["preview"]
    assert preview.kind == ActionPreviewKind.CODE_DIFF
    assert preview.task_id == "task-hitl-002"
    assert preview.requires_approval is True
    assert payload["step_id"] == "step-2"
    assert payload["attempt_id"] == "att-1"
    assert payload["subagent_id"] == "subagent-code-1"
    assert payload["machine_policy_allowed"] is True
    assert len(payload["input_snapshot_hash"]) == 64
    assert len(payload["output_snapshot_hash"]) == 64
    assert len(payload["review_dossier_hash"]) == 64


# ===========================================================================
# 3. Reviewer Role Screening
# ===========================================================================

def test_reviewer_role_screening(hitl_coordinator: HitlCoordinator) -> None:
    """Authorized roles pass; unauthorized roles fail fail-closed."""
    valid_roles = ["engineering", "admin", "tech_lead", "lead_engineer", "brand_lead"]
    invalid_roles = ["guest", "marketing", "finance", "external_contractor", "intern"]

    for role in valid_roles:
        token = hitl_coordinator.decide_development_step(
            task_id="task-role",
            workflow_id="wf-role",
            step_id="step-1",
            attempt_id=f"att-{role}",
            subagent_id="subagent-1",
            reviewer_id=f"user-{role}",
            reviewer_role=role,
            decision="APPROVE",
            input_snapshot_hash="in-hash",
            output_snapshot_hash="out-hash",
            review_dossier_hash="dossier-hash",
        )
        assert token.decision == "APPROVE"
        assert token.reviewer_role == role

    for role in invalid_roles:
        with pytest.raises(PolicyViolationError, match="is not authorized to"):
            hitl_coordinator.decide_development_step(
                task_id="task-role",
                workflow_id="wf-role",
                step_id="step-1",
                attempt_id=f"att-{role}",
                subagent_id="subagent-1",
                reviewer_id=f"user-{role}",
                reviewer_role=role,
                decision="APPROVE",
                input_snapshot_hash="in-hash",
                output_snapshot_hash="out-hash",
                review_dossier_hash="dossier-hash",
            )


# ===========================================================================
# 4. Ed25519 Cryptographic Binding & Tampering Rejection
# ===========================================================================

def test_approval_token_ed25519_binding(
    hitl_coordinator: HitlCoordinator, ed25519_key_pems: tuple[str, str]
) -> None:
    """Approval token is signed with Ed25519; any modification invalidates signature."""
    private_pem, public_pem = ed25519_key_pems

    token = hitl_coordinator.decide_development_step(
        task_id="task-crypto",
        workflow_id="wf-crypto",
        step_id="step-crypto-1",
        attempt_id="att-crypto-1",
        subagent_id="subagent-crypto-1",
        reviewer_id="lead-engineer-1",
        reviewer_role="lead_engineer",
        decision="APPROVE",
        input_snapshot_hash="hash-input-123",
        output_snapshot_hash="hash-output-456",
        review_dossier_hash="hash-dossier-789",
        private_key_pem=private_pem,
    )

    # 1. Verify valid signature with correct public key
    assert token.signature is not None
    assert token.verify_signature(public_key_pem=public_pem) is True

    # 2. Tampering with output hash breaks signature verification
    tampered_output = token.model_copy(update={"output_snapshot_hash": "tampered-output-hash"})
    assert tampered_output.verify_signature(public_key_pem=public_pem) is False

    # 3. Tampering with task_id breaks signature verification
    tampered_task = token.model_copy(update={"task_id": "other-task-id"})
    assert tampered_task.verify_signature(public_key_pem=public_pem) is False

    # 4. Tampering with decision breaks signature verification
    tampered_decision = token.model_copy(update={"decision": "REJECT"})
    assert tampered_decision.verify_signature(public_key_pem=public_pem) is False


# ===========================================================================
# 5. Deterministic Precedence: Machine DENY + Human APPROVE = DENY
# ===========================================================================

def test_machine_deny_human_approve_fails_closed(
    hitl_coordinator: HitlCoordinator, state_machine: DevelopmentStateMachine
) -> None:
    """Machine policy DENY overrides human APPROVE fail-closed."""
    # 1. HitlCoordinator blocks creation of approved token when machine policy denied
    with pytest.raises(PolicyViolationError, match="Machine policy violation"):
        hitl_coordinator.decide_development_step(
            task_id="task-deny",
            workflow_id="wf-deny",
            step_id="step-1",
            attempt_id="att-1",
            subagent_id="subagent-1",
            reviewer_id="admin-1",
            reviewer_role="admin",
            decision="APPROVE",
            input_snapshot_hash="in-hash",
            output_snapshot_hash="out-hash",
            review_dossier_hash="dossier-hash",
            machine_policy_allowed=False,
        )

    # 2. State machine transition to APPROVED is rejected if machine_policy_allowed is False
    with pytest.raises(PolicyViolationError, match="Machine policy denied this step"):
        state_machine.validate_transition_guards(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            step_id="step-1",
            attempt_id="att-1",
            state_data={
                "approval_decision": "APPROVE",
                "machine_policy_allowed": False,
            },
        )


# ===========================================================================
# 6. Tampered Candidate Payload Hash Mismatch
# ===========================================================================

def test_tampered_payload_hash_mismatch(
    hitl_coordinator: HitlCoordinator,
    state_machine: DevelopmentStateMachine,
    ed25519_key_pems: tuple[str, str],
) -> None:
    """Approval token candidate hash must match state candidate hash."""
    private_pem, public_pem = ed25519_key_pems

    token = hitl_coordinator.decide_development_step(
        task_id="task-mismatch",
        workflow_id="wf-mismatch",
        step_id="step-1",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-1",
        reviewer_role="engineering",
        decision="APPROVE",
        input_snapshot_hash="in-hash",
        output_snapshot_hash="candidate-hash-A",
        review_dossier_hash="dossier-hash",
        private_key_pem=private_pem,
    )

    # State machine candidate hash is "candidate-hash-B" (different from token's "candidate-hash-A")
    with pytest.raises(PolicyViolationError, match="candidate hash mismatch"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id="task-mismatch",
            workflow_id="wf-mismatch",
            step_id="step-1",
            attempt_id="att-1",
            idempotency_key="approve-tamper",
            state_data={
                "candidate_hash": "candidate-hash-B",
                "approval_token": token,
                "approval_decision": "APPROVE",
            },
        )


# ===========================================================================
# 7. Step and Attempt Mismatch Rejection
# ===========================================================================

def test_attempt_step_mismatch_rejection(
    hitl_coordinator: HitlCoordinator, state_machine: DevelopmentStateMachine
) -> None:
    """Approval token bound to Step 1 Attempt 1 cannot approve Step 2 or Attempt 2."""
    token = hitl_coordinator.decide_development_step(
        task_id="task-cross",
        workflow_id="wf-cross",
        step_id="step-1",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-1",
        reviewer_role="engineering",
        decision="APPROVE",
        input_snapshot_hash="in-hash",
        output_snapshot_hash="out-hash",
        review_dossier_hash="dossier-hash",
    )

    # Step mismatch
    with pytest.raises(PolicyViolationError, match="token step_id mismatch"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id="task-cross",
            workflow_id="wf-cross",
            step_id="step-2",
            attempt_id="att-1",
            idempotency_key="approve-step-mismatch",
            state_data={
                "candidate_hash": "out-hash",
                "approval_token": token,
                "approval_decision": "APPROVE",
            },
        )

    # Attempt mismatch
    with pytest.raises(PolicyViolationError, match="token attempt_id mismatch"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id="task-cross",
            workflow_id="wf-cross",
            step_id="step-1",
            attempt_id="att-2",
            idempotency_key="approve-attempt-mismatch",
            state_data={
                "candidate_hash": "out-hash",
                "approval_token": token,
                "approval_decision": "APPROVE",
            },
        )


# ===========================================================================
# 8. Replay Prevention for Token IDs and Nonces
# ===========================================================================

def test_approval_token_replay_rejected(hitl_coordinator: HitlCoordinator) -> None:
    """Reusing nonce or replay is rejected fail-closed."""
    fixed_nonce = "fixed-unique-nonce-12345"

    # First decision with nonce succeeds
    hitl_coordinator.decide_development_step(
        task_id="task-replay",
        workflow_id="wf-replay",
        step_id="step-1",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-1",
        reviewer_role="engineering",
        decision="APPROVE",
        input_snapshot_hash="in-hash",
        output_snapshot_hash="out-hash",
        review_dossier_hash="dossier-hash",
        nonce=fixed_nonce,
    )

    # Second decision with same nonce fails replay check
    with pytest.raises(PolicyViolationError, match="Replay detected"):
        hitl_coordinator.decide_development_step(
            task_id="task-replay",
            workflow_id="wf-replay",
            step_id="step-1",
            attempt_id="att-2",
            subagent_id="subagent-1",
            reviewer_id="eng-1",
            reviewer_role="engineering",
            decision="APPROVE",
            input_snapshot_hash="in-hash",
            output_snapshot_hash="out-hash",
            review_dossier_hash="dossier-hash",
            nonce=fixed_nonce,
        )


# ===========================================================================
# 9. Token Expiry Enforcement
# ===========================================================================

def test_approval_token_expiry(state_machine: DevelopmentStateMachine) -> None:
    """Expired approval token is rejected by transition guards."""
    expired_token = DevelopmentApprovalToken(
        task_id="task-exp",
        workflow_id="wf-exp",
        step_id="step-1",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-1",
        reviewer_role="engineering",
        decision="APPROVE",
        input_snapshot_hash="in-hash",
        output_snapshot_hash="out-hash",
        review_dossier_hash="dossier-hash",
        created_at=datetime.now(UTC) - timedelta(hours=2),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert expired_token.is_expired() is True

    with pytest.raises(PolicyViolationError, match="Approval token has expired"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id="task-exp",
            workflow_id="wf-exp",
            step_id="step-1",
            attempt_id="att-1",
            idempotency_key="approve-expired",
            state_data={
                "candidate_hash": "out-hash",
                "approval_token": expired_token,
                "approval_decision": "APPROVE",
            },
        )


# ===========================================================================
# 10. Rejection and Revision Routing
# ===========================================================================

def test_rejection_leads_to_correction_required(
    hitl_coordinator: HitlCoordinator, state_machine: DevelopmentStateMachine
) -> None:
    """Human REJECT decision transitions HITL_PENDING -> CORRECTION_REQUIRED -> RETRY_PREPARED."""
    rejection_token = hitl_coordinator.decide_development_step(
        task_id="task-reject",
        workflow_id="wf-reject",
        step_id="step-1",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-lead",
        reviewer_role="tech_lead",
        decision="REJECT",
        input_snapshot_hash="in-hash",
        output_snapshot_hash="out-hash",
        review_dossier_hash="dossier-hash",
        revision_notes="Unit tests missing for edge cases.",
    )

    # 1. Rejection token cannot be used to transition to APPROVED
    with pytest.raises(PolicyViolationError, match="token decision is 'REJECT'"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            task_id="task-reject",
            workflow_id="wf-reject",
            step_id="step-1",
            attempt_id="att-1",
            idempotency_key="illegal-approve",
            state_data={
                "candidate_hash": "out-hash",
                "approval_token": rejection_token,
            },
        )

    # 2. Transition from HITL_PENDING to CORRECTION_REQUIRED succeeds
    cp_corr = state_machine.transition(
        current_state=DevelopmentWorkflowState.HITL_PENDING,
        target_state=DevelopmentWorkflowState.CORRECTION_REQUIRED,
        task_id="task-reject",
        workflow_id="wf-reject",
        step_id="step-1",
        attempt_id="att-1",
        idempotency_key="corr-1",
        state_data={
            "approval_token": rejection_token,
            "approval_decision": "REJECT",
            "revision_notes": rejection_token.revision_notes,
        },
    )
    assert cp_corr.state == DevelopmentWorkflowState.CORRECTION_REQUIRED

    # 3. Transition from CORRECTION_REQUIRED to RETRY_PREPARED succeeds
    cp_retry = state_machine.transition(
        current_state=DevelopmentWorkflowState.CORRECTION_REQUIRED,
        target_state=DevelopmentWorkflowState.RETRY_PREPARED,
        task_id="task-reject",
        workflow_id="wf-reject",
        step_id="step-1",
        attempt_id="att-1",
        idempotency_key="retry-1",
        error="HITL rejection: Unit tests missing for edge cases.",
        current_retries=0,
    )
    assert cp_retry.state == DevelopmentWorkflowState.RETRY_PREPARED


# ===========================================================================
# 11. Restart-Safe State Persistence and Recovery
# ===========================================================================

@pytest.mark.asyncio
async def test_restart_safe_recovery_with_approval(
    hitl_coordinator: HitlCoordinator,
    state_machine: DevelopmentStateMachine,
    active_lease: DevelopmentExecutionLease,
) -> None:
    """Approval token and state persist in CTS and survive service reboots."""
    repo = FakeTaskStateRepository()
    service1 = TaskStateService(repository=repo)

    task_id = "task-persist-001"
    wf_id = "wf-persist-001"

    # 1. Create task in repository
    initial_task = CanonicalTaskState(
        task_id=task_id,
        directive_id="dir-persist",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.IN_PROGRESS,
    )
    await repo.save_state("tenant-1", initial_task)

    # 2. Save HITL_PENDING checkpoint
    cand_hash = "sha256-cand-hash-persist"
    cp_pending = state_machine.transition(
        current_state=DevelopmentWorkflowState.RESULT_SEALED,
        target_state=DevelopmentWorkflowState.HITL_PENDING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-dev-impl",
        attempt_id="att-1",
        idempotency_key="pending-persist",
        state_data={"candidate_hash": cand_hash},
    )
    await service1.save_development_checkpoint("tenant-1", cp_pending)

    # 3. Issue approval token and record it
    token = hitl_coordinator.decide_development_step(
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-dev-impl",
        attempt_id="att-1",
        subagent_id="subagent-1",
        reviewer_id="eng-lead",
        reviewer_role="tech_lead",
        decision="APPROVE",
        input_snapshot_hash="in-hash",
        output_snapshot_hash=cand_hash,
        review_dossier_hash="dossier-hash",
    )
    await service1.record_development_approval_decision("tenant-1", task_id, token)

    # 4. Simulate process crash/restart: create fresh TaskStateService over same repository
    service2 = TaskStateService(repository=repo)
    recovered_cp, state_data = await service2.resume_development_workflow("tenant-1", task_id)
    assert recovered_cp.state == DevelopmentWorkflowState.HITL_PENDING

    recovered_token = await service2.get_development_approval_token(task_id, "step-dev-impl", "att-1")
    assert recovered_token is not None
    assert recovered_token.decision == "APPROVE"
    assert recovered_token.token_id == token.token_id

    # 5. Successfully advance state to APPROVED using recovered token
    cp_approved = state_machine.transition(
        current_state=recovered_cp.state,
        target_state=DevelopmentWorkflowState.APPROVED,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-dev-impl",
        attempt_id="att-1",
        idempotency_key="approve-recovered",
        state_data={
            "candidate_hash": cand_hash,
            "approval_token": recovered_token,
            "approval_decision": recovered_token.decision,
        },
    )
    assert cp_approved.state == DevelopmentWorkflowState.APPROVED


# ===========================================================================
# 12. Transport API Route POST /api/v1/approvals/development/decide
# ===========================================================================

def test_api_route_development_decide() -> None:
    """Test transport route /api/v1/approvals/development/decide."""
    app = create_app()
    client = TestClient(app)

    request_payload = {
        "task_id": "task-api-001",
        "workflow_id": "wf-api-001",
        "step_id": "step-api-1",
        "attempt_id": "att-api-1",
        "subagent_id": "subagent-1",
        "reviewer_id": "eng-user-1",
        "reviewer_role": "engineering",
        "decision": "APPROVE",
        "input_snapshot_hash": "a" * 64,
        "output_snapshot_hash": "b" * 64,
        "review_dossier_hash": "c" * 64,
        "version": "1.0",
        "machine_policy_allowed": True,
        "expires_in_seconds": 3600,
    }

    response = client.post("/approvals/development/decide", json=request_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["task_id"] == "task-api-001"
    assert data["decision"] == "APPROVE"
    assert data["approved"] is True
    assert "token_id" in data
    assert "signature" in data
    assert len(data["signature"]) > 0
