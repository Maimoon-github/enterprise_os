"""Deterministic Sequential State Machine for W_DEV (DE-02).

Enforces:
- Canonical sequential development states
- max_concurrency = 1 (single active sub-agent invariant)
- Transition guards: predecessor verification, lease ownership, unexpired grant, retry budget
- Bounded retries for classified transient failures
- Durable checkpoint creation with idempotency keys
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import InvalidTransitionError, PolicyViolationError
from app.core.logging import get_logger
from app.schemas.task_state import (
    DevelopmentExecutionLease,
    DevelopmentWorkflowCheckpoint,
    DevelopmentWorkflowState,
    RetryClassification,
    WorkflowRetryPolicy,
)

logger = get_logger(__name__)

_ALLOWED_TRANSITIONS: dict[DevelopmentWorkflowState, frozenset[DevelopmentWorkflowState]] = {
    DevelopmentWorkflowState.RECEIVED: frozenset(
        {
            DevelopmentWorkflowState.POLICY_BOUND,
            DevelopmentWorkflowState.ABORTED,
            DevelopmentWorkflowState.FAILED,
        }
    ),
    DevelopmentWorkflowState.POLICY_BOUND: frozenset(
        {
            DevelopmentWorkflowState.PLANNING,
            DevelopmentWorkflowState.ABORTED,
            DevelopmentWorkflowState.FAILED,
        }
    ),
    DevelopmentWorkflowState.PLANNING: frozenset(
        {
            DevelopmentWorkflowState.RESULT_SEALED,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.RESULT_SEALED: frozenset(
        {
            DevelopmentWorkflowState.HITL_PENDING,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.HITL_PENDING: frozenset(
        {
            DevelopmentWorkflowState.APPROVED,
            DevelopmentWorkflowState.CORRECTION_REQUIRED,
            DevelopmentWorkflowState.ABORTED,
            DevelopmentWorkflowState.FAILED,
        }
    ),
    DevelopmentWorkflowState.APPROVED: frozenset(
        {
            DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            DevelopmentWorkflowState.NEXT_STEP,
            DevelopmentWorkflowState.RELEASE_READY,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.CORRECTION_REQUIRED: frozenset(
        {
            DevelopmentWorkflowState.RETRY_PREPARED,
            DevelopmentWorkflowState.ABORTED,
            DevelopmentWorkflowState.FAILED,
        }
    ),
    DevelopmentWorkflowState.RETRY_PREPARED: frozenset(
        {
            DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            DevelopmentWorkflowState.PLANNING,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.SANDBOX_PROVISIONING: frozenset(
        {
            DevelopmentWorkflowState.VALIDATED,
            DevelopmentWorkflowState.SUBAGENT_RUNNING,
            DevelopmentWorkflowState.RETRY_PREPARED,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.VALIDATED: frozenset(
        {
            DevelopmentWorkflowState.SUBAGENT_RUNNING,
            DevelopmentWorkflowState.RETRY_PREPARED,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.SUBAGENT_RUNNING: frozenset(
        {
            DevelopmentWorkflowState.RESULT_SEALED,
            DevelopmentWorkflowState.RETRY_PREPARED,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.NEXT_STEP: frozenset(
        {
            DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            DevelopmentWorkflowState.RELEASE_READY,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.RELEASE_READY: frozenset(
        {
            DevelopmentWorkflowState.COMPLETED,
            DevelopmentWorkflowState.FAILED,
            DevelopmentWorkflowState.ABORTED,
        }
    ),
    DevelopmentWorkflowState.COMPLETED: frozenset(),
    DevelopmentWorkflowState.FAILED: frozenset(
        {
            DevelopmentWorkflowState.RETRY_PREPARED,
        }
    ),
    DevelopmentWorkflowState.ABORTED: frozenset(),
}

TRANSIENT_EXCEPTIONS = (
    "TimeoutError",
    "TransientWorkflowError",
    "LeaseContentionError",
    "SandboxProvisioningError",
    "SandboxValidationError",
    "SandboxIsolationError",
    "SandboxExecutionError",
    "ConnectionError",
)


class DevelopmentStateMachine:
    """Deterministic, durable sequential state machine for W_DEV."""

    def __init__(self, retry_policy: WorkflowRetryPolicy | None = None) -> None:
        self.retry_policy = retry_policy or WorkflowRetryPolicy()

    def legal_next_states(
        self, current: DevelopmentWorkflowState
    ) -> frozenset[DevelopmentWorkflowState]:
        """Return the set of valid successor states from current state."""
        return _ALLOWED_TRANSITIONS.get(current, frozenset())

    def can_transition(
        self, current: DevelopmentWorkflowState, target: DevelopmentWorkflowState
    ) -> bool:
        """Check if transition from current to target is allowed."""
        return target in self.legal_next_states(current)

    def classify_error(self, error: Exception | str) -> RetryClassification:
        """Classify error into retry-eligible transient vs permanent."""
        err_str = str(error)
        err_type = type(error).__name__ if isinstance(error, Exception) else err_str

        if any(t in err_type or t in err_str for t in TRANSIENT_EXCEPTIONS):
            return RetryClassification.TRANSIENT
        if "security" in err_str.lower() or "traversal" in err_str.lower():
            return RetryClassification.SECURITY_BLOCK
        if "rejection" in err_str.lower() or "rejected" in err_str.lower():
            return RetryClassification.HITL_REJECTION
        return RetryClassification.PERMANENT

    def can_retry(
        self,
        current_retries: int,
        error: Exception | str | None = None,
    ) -> bool:
        """Check whether task may be retried under retry budget and classification."""
        if current_retries >= self.retry_policy.max_retries:
            return False
        if error is not None:
            classification = self.classify_error(error)
            return classification == RetryClassification.TRANSIENT
        return True

    def validate_transition_guards(
        self,
        *,
        current_state: DevelopmentWorkflowState,
        target_state: DevelopmentWorkflowState,
        step_id: str | None = None,
        attempt_id: str | None = None,
        lease: DevelopmentExecutionLease | None = None,
        expected_owner: str | None = None,
        active_subagent_count: int = 0,
        grant_expired: bool = False,
        state_data: dict[str, Any] | None = None,
        error: Exception | str | None = None,
        current_retries: int = 0,
    ) -> None:
        """Evaluate transition guards fail-closed."""
        # 1. State machine legality
        if not self.can_transition(current_state, target_state):
            raise InvalidTransitionError(
                f"Illegal transition from {current_state.value} to {target_state.value}. "
                f"Allowed successors: {[s.value for s in self.legal_next_states(current_state)]}"
            )

        # 2. Grant expiration check
        if grant_expired:
            raise PolicyViolationError(
                f"Transition to {target_state.value} rejected: Development task grant has expired."
            )

        # 3. Single-active-subagent invariant (max_concurrency = 1)
        if target_state == DevelopmentWorkflowState.SUBAGENT_RUNNING:
            if active_subagent_count > 0:
                raise PolicyViolationError(
                    f"Max concurrency violation: Cannot enter SUBAGENT_RUNNING with "
                    f"{active_subagent_count} already active sub-agent(s). Maximum concurrency is 1."
                )

        # 4. Lease verification for sub-agent execution & sealing
        if target_state in (
            DevelopmentWorkflowState.VALIDATED,
            DevelopmentWorkflowState.SUBAGENT_RUNNING,
            DevelopmentWorkflowState.RESULT_SEALED,
        ):
            if lease is None:
                raise PolicyViolationError(
                    f"Transition to {target_state.value} rejected: Execution lease is required."
                )
            if lease.is_expired():
                raise PolicyViolationError(
                    f"Transition to {target_state.value} rejected: Execution lease {lease.lease_id} has expired."
                )
            if expected_owner and lease.owner_id != expected_owner:
                raise PolicyViolationError(
                    f"Transition to {target_state.value} rejected: Lease owner mismatch. "
                    f"Expected '{expected_owner}', held by '{lease.owner_id}'."
                )

        # 5. Isolation validation guard before execution
        state_data = state_data or {}
        if target_state == DevelopmentWorkflowState.SUBAGENT_RUNNING:
            if state_data.get("isolation_validated") is False:
                raise PolicyViolationError(
                    "Transition to SUBAGENT_RUNNING rejected: Sandbox isolation validation failed."
                )

        # 6. Retry budget guard
        if target_state == DevelopmentWorkflowState.RETRY_PREPARED:
            if current_state == DevelopmentWorkflowState.CORRECTION_REQUIRED:
                if current_retries >= self.retry_policy.max_retries:
                    raise PolicyViolationError(
                        f"Cannot prepare retry: Budget exhausted ({current_retries}/{self.retry_policy.max_retries})."
                    )
            else:
                if not self.can_retry(current_retries, error):
                    classification = self.classify_error(error) if error else "MAX_RETRIES_EXCEEDED"
                    raise PolicyViolationError(
                        f"Cannot prepare retry: Budget exhausted ({current_retries}/{self.retry_policy.max_retries}) "
                        f"or error classification is non-transient ({classification})."
                    )

        # 7. Required state data presence & HITL guards
        state_data = state_data or {}
        if target_state == DevelopmentWorkflowState.HITL_PENDING:
            if not state_data.get("candidate_hash") and not state_data.get("deliverable"):
                raise PolicyViolationError(
                    "Transition to HITL_PENDING requires candidate_hash or deliverable in state data."
                )
        elif target_state == DevelopmentWorkflowState.APPROVED:
            # Enforce machine DENY + human APPROVE = DENY
            if state_data.get("machine_policy_allowed") is False:
                raise PolicyViolationError(
                    "Transition to APPROVED blocked: Machine policy denied this step. "
                    "Machine policy takes precedence over human approval."
                )

            dossier = state_data.get("verification_dossier") or state_data.get("dossier")
            if dossier is not None:
                dossier_verdict = getattr(dossier, "verdict", None) or (
                    dossier.get("verdict") if isinstance(dossier, dict) else None
                )
                if dossier_verdict and str(dossier_verdict) != "PASS":
                    raise PolicyViolationError(
                        "Transition to APPROVED blocked: Verification dossier verdict is "
                        f"'{dossier_verdict}' (must be 'PASS' to advance to DEV-SEC)."
                    )

            sec_dossier = state_data.get("security_dossier")
            if sec_dossier is not None:
                sec_verdict = getattr(sec_dossier, "verdict", None) or (
                    sec_dossier.get("verdict") if isinstance(sec_dossier, dict) else None
                )
                hard_blocks = getattr(sec_dossier, "hard_block_count", 0) or (
                    sec_dossier.get("hard_block_count", 0)
                    if isinstance(sec_dossier, dict)
                    else 0
                )
                if (sec_verdict and str(sec_verdict) != "PASS") or hard_blocks > 0:
                    raise PolicyViolationError(
                        "Transition to APPROVED blocked: Security dossier verdict is "
                        f"'{sec_verdict}' with {hard_blocks} hard-block findings "
                        "(must be 'PASS' with 0 hard blocks to advance to DEV-REL). "
                        "Machine DENY overrides human approval."
                    )

            token = state_data.get("approval_token")
            decision = state_data.get("approval_decision")

            if not token and not decision:
                raise PolicyViolationError(
                    "Transition to APPROVED requires approval_token or approval_decision in state data."
                )
            if decision and decision != "APPROVE":
                raise PolicyViolationError(
                    f"Transition to APPROVED rejected: approval_decision is '{decision}', expected 'APPROVE'."
                )

            if token is not None:
                tok_decision = getattr(token, "decision", None) or (
                    token.get("decision") if isinstance(token, dict) else None
                )
                if tok_decision and tok_decision != "APPROVE":
                    raise PolicyViolationError(
                        f"Transition to APPROVED rejected: token decision is '{tok_decision}', expected 'APPROVE'."
                    )

                tok_step = getattr(token, "step_id", None) or (
                    token.get("step_id") if isinstance(token, dict) else None
                )
                expected_step = step_id or state_data.get("step_id")
                if expected_step and tok_step and tok_step != expected_step:
                    raise PolicyViolationError(
                        f"Transition to APPROVED rejected: token step_id mismatch. "
                        f"Expected '{expected_step}', got '{tok_step}'."
                    )

                tok_attempt = getattr(token, "attempt_id", None) or (
                    token.get("attempt_id") if isinstance(token, dict) else None
                )
                expected_attempt = attempt_id or state_data.get("attempt_id")
                if expected_attempt and tok_attempt and tok_attempt != expected_attempt:
                    raise PolicyViolationError(
                        f"Transition to APPROVED rejected: token attempt_id mismatch. "
                        f"Expected '{expected_attempt}', got '{tok_attempt}'."
                    )

                cand_hash = state_data.get("candidate_hash") or state_data.get(
                    "output_snapshot_hash"
                )
                tok_hash = getattr(token, "output_snapshot_hash", None) or getattr(
                    token, "candidate_hash", None
                )
                if not tok_hash and isinstance(token, dict):
                    tok_hash = token.get("output_snapshot_hash") or token.get("candidate_hash")
                if cand_hash and tok_hash and cand_hash != tok_hash:
                    raise PolicyViolationError(
                        f"Transition to APPROVED rejected: candidate hash mismatch. "
                        f"Expected '{cand_hash}', token has '{tok_hash}'."
                    )

                # Check token expiry
                is_expired = False
                if hasattr(token, "is_expired") and callable(token.is_expired):
                    is_expired = token.is_expired()
                elif isinstance(token, dict) and "expires_at" in token:
                    exp = token["expires_at"]
                    if isinstance(exp, str):
                        exp = datetime.fromisoformat(exp)
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=UTC)
                    is_expired = datetime.now(UTC) > exp

                if is_expired:
                    raise PolicyViolationError(
                        "Transition to APPROVED rejected: Approval token has expired."
                    )

                # Check token signature if validator or public_key_pem is configured
                validator = state_data.get("validator")
                public_key_pem = state_data.get("public_key_pem")
                if (
                    (validator or public_key_pem)
                    and hasattr(token, "verify_signature")
                    and callable(token.verify_signature)
                    and getattr(token, "signature", None)
                ):
                    if not token.verify_signature(
                        validator=validator, public_key_pem=public_key_pem
                    ):
                        raise PolicyViolationError(
                            "Transition to APPROVED rejected: Approval token signature verification failed."
                        )

        elif target_state == DevelopmentWorkflowState.CORRECTION_REQUIRED:
            token = state_data.get("approval_token")
            decision = state_data.get("approval_decision")
            tok_decision = (
                getattr(token, "decision", None)
                or (token.get("decision") if isinstance(token, dict) else None)
                if token
                else None
            )
            actual_decision = decision or tok_decision
            if actual_decision not in ("REJECT", "REQUEST_REVISION"):
                raise PolicyViolationError(
                    f"Transition to CORRECTION_REQUIRED requires decision in ('REJECT', 'REQUEST_REVISION'), "
                    f"got '{actual_decision}'."
                )

        elif (
            target_state == DevelopmentWorkflowState.RELEASE_READY
            and not state_data.get("release_candidate")
            and not state_data.get("release_hash")
        ):
            raise PolicyViolationError(
                "Transition to RELEASE_READY requires release_candidate or "
                "release_hash in state data."
            )

        # 8. Provenance & Audit fail-closed transition guard (DE-05)
        if state_data.get("provenance_recording_failed") is True:
            raise PolicyViolationError(
                f"Transition to {target_state.value} rejected: Provenance recording failed. "
                "Execution fails closed when audit lineage cannot be guaranteed."
            )
        if target_state in (
            DevelopmentWorkflowState.NEXT_STEP,
            DevelopmentWorkflowState.RELEASE_READY,
            DevelopmentWorkflowState.COMPLETED,
        ):
            if state_data.get("provenance_verified") is False:
                raise PolicyViolationError(
                    f"Transition to {target_state.value} rejected: Provenance verification failed. "
                    "Cannot advance workflow without valid tamper-evident audit lineage."
                )

    def transition(
        self,
        *,
        current_state: DevelopmentWorkflowState,
        target_state: DevelopmentWorkflowState,
        task_id: str,
        workflow_id: str,
        step_id: str,
        attempt_id: str,
        idempotency_key: str,
        lease: DevelopmentExecutionLease | None = None,
        expected_owner: str | None = None,
        active_subagent_count: int = 0,
        grant_expired: bool = False,
        state_data: dict[str, Any] | None = None,
        error: Exception | str | None = None,
        current_retries: int = 0,
        active_subagent: str | None = None,
    ) -> DevelopmentWorkflowCheckpoint:
        """Validate guards, advance state, and generate an immutable checkpoint."""
        self.validate_transition_guards(
            current_state=current_state,
            target_state=target_state,
            step_id=step_id,
            attempt_id=attempt_id,
            lease=lease,
            expected_owner=expected_owner,
            active_subagent_count=active_subagent_count,
            grant_expired=grant_expired,
            state_data=state_data,
            error=error,
            current_retries=current_retries,
        )

        checkpoint = DevelopmentWorkflowCheckpoint(
            checkpoint_id=str(uuid.uuid4()),
            task_id=task_id,
            workflow_id=workflow_id,
            step_id=step_id,
            attempt_id=attempt_id,
            state=target_state,
            idempotency_key=idempotency_key,
            state_data=state_data or {},
            active_subagent=active_subagent,
            recorded_at=datetime.now(UTC),
        )

        logger.info(
            "W_DEV state transition committed",
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "prev_state": current_state.value,
                "new_state": target_state.value,
                "checkpoint_id": checkpoint.checkpoint_id,
                "idempotency_key": idempotency_key,
            },
        )
        return checkpoint

    async def transition_with_provenance(
        self,
        *,
        current_state: DevelopmentWorkflowState,
        target_state: DevelopmentWorkflowState,
        task_id: str,
        workflow_id: str,
        step_id: str,
        attempt_id: str,
        idempotency_key: str,
        provenance_recorder: Any,
        tenant_id: str = "default",
        input_snapshot_hash: str = "0" * 32,
        output_snapshot_hash: str | None = None,
        artifact_hashes: dict[str, str] | None = None,
        lease: DevelopmentExecutionLease | None = None,
        expected_owner: str | None = None,
        active_subagent_count: int = 0,
        grant_expired: bool = False,
        state_data: dict[str, Any] | None = None,
        error: Exception | str | None = None,
        current_retries: int = 0,
        active_subagent: str | None = None,
        raw_prompt: str | None = None,
    ) -> DevelopmentWorkflowCheckpoint:
        """Validate guards, record tamper-evident provenance event fail-closed, and commit checkpoint."""
        s_data = dict(state_data or {})

        self.validate_transition_guards(
            current_state=current_state,
            target_state=target_state,
            step_id=step_id,
            attempt_id=attempt_id,
            lease=lease,
            expected_owner=expected_owner,
            active_subagent_count=active_subagent_count,
            grant_expired=grant_expired,
            state_data=s_data,
            error=error,
            current_retries=current_retries,
        )

        try:
            if provenance_recorder and hasattr(provenance_recorder, "record_development_event"):
                eff_in_hash = s_data.get("input_snapshot_hash") or input_snapshot_hash
                eff_out_hash = (
                    output_snapshot_hash
                    or s_data.get("candidate_hash")
                    or s_data.get("output_snapshot_hash")
                )
                eff_art_hashes = artifact_hashes or s_data.get("artifact_hashes") or {}
                prov_ev = await provenance_recorder.record_development_event(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    workflow_id=workflow_id,
                    step_id=step_id,
                    attempt_id=attempt_id,
                    activity_type=f"transition_{target_state.value.lower()}",
                    agent_id=active_subagent or "W_DEV",
                    worker_role="W_DEV",
                    input_snapshot_hash=eff_in_hash,
                    output_snapshot_hash=eff_out_hash,
                    artifact_hashes=eff_art_hashes,
                    action_digest=s_data.get("action_digest"),
                    status="SUCCESS",
                    raw_prompt=raw_prompt,
                    metadata={
                        "from_state": current_state.value,
                        "to_state": target_state.value,
                        "idempotency_key": idempotency_key,
                        **s_data,
                    },
                )
                s_data["provenance_event_id"] = prov_ev.event_id
                s_data["provenance_event_hash"] = prov_ev.event_hash
                s_data["provenance_signature"] = prov_ev.control_plane_signature
                s_data["provenance_verified"] = True
        except Exception as exc:
            s_data["provenance_recording_failed"] = True
            raise PolicyViolationError(
                f"Fail-closed guard: failed to record provenance event during transition to {target_state.value}: {exc}"
            ) from exc

        return self.transition(
            current_state=current_state,
            target_state=target_state,
            task_id=task_id,
            workflow_id=workflow_id,
            step_id=step_id,
            attempt_id=attempt_id,
            idempotency_key=idempotency_key,
            lease=lease,
            expected_owner=expected_owner,
            active_subagent_count=active_subagent_count,
            grant_expired=grant_expired,
            state_data=s_data,
            error=error,
            current_retries=current_retries,
            active_subagent=active_subagent,
        )
