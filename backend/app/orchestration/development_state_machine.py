"""Deterministic Sequential State Machine for W_DEV (DE-02).

Enforces:
- Canonical sequential development states
- max_concurrency = 1 (single active sub-agent invariant)
- Transition guards: predecessor verification, lease ownership, unexpired grant, retry budget
- Bounded retries for classified transient failures
- Durable checkpoint creation with idempotency keys
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

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
    DevelopmentWorkflowState.RECEIVED: frozenset({
        DevelopmentWorkflowState.POLICY_BOUND,
        DevelopmentWorkflowState.ABORTED,
        DevelopmentWorkflowState.FAILED,
    }),
    DevelopmentWorkflowState.POLICY_BOUND: frozenset({
        DevelopmentWorkflowState.PLANNING,
        DevelopmentWorkflowState.ABORTED,
        DevelopmentWorkflowState.FAILED,
    }),
    DevelopmentWorkflowState.PLANNING: frozenset({
        DevelopmentWorkflowState.RESULT_SEALED,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.RESULT_SEALED: frozenset({
        DevelopmentWorkflowState.HITL_PENDING,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.HITL_PENDING: frozenset({
        DevelopmentWorkflowState.APPROVED,
        DevelopmentWorkflowState.CORRECTION_REQUIRED,
        DevelopmentWorkflowState.ABORTED,
        DevelopmentWorkflowState.FAILED,
    }),
    DevelopmentWorkflowState.APPROVED: frozenset({
        DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        DevelopmentWorkflowState.NEXT_STEP,
        DevelopmentWorkflowState.RELEASE_READY,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.CORRECTION_REQUIRED: frozenset({
        DevelopmentWorkflowState.RETRY_PREPARED,
        DevelopmentWorkflowState.ABORTED,
        DevelopmentWorkflowState.FAILED,
    }),
    DevelopmentWorkflowState.RETRY_PREPARED: frozenset({
        DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        DevelopmentWorkflowState.PLANNING,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.SANDBOX_PROVISIONING: frozenset({
        DevelopmentWorkflowState.SUBAGENT_RUNNING,
        DevelopmentWorkflowState.RETRY_PREPARED,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.SUBAGENT_RUNNING: frozenset({
        DevelopmentWorkflowState.RESULT_SEALED,
        DevelopmentWorkflowState.RETRY_PREPARED,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.NEXT_STEP: frozenset({
        DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        DevelopmentWorkflowState.RELEASE_READY,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.RELEASE_READY: frozenset({
        DevelopmentWorkflowState.COMPLETED,
        DevelopmentWorkflowState.FAILED,
        DevelopmentWorkflowState.ABORTED,
    }),
    DevelopmentWorkflowState.COMPLETED: frozenset(),
    DevelopmentWorkflowState.FAILED: frozenset({
        DevelopmentWorkflowState.RETRY_PREPARED,
    }),
    DevelopmentWorkflowState.ABORTED: frozenset(),
}

TRANSIENT_EXCEPTIONS = (
    "TimeoutError",
    "TransientWorkflowError",
    "LeaseContentionError",
    "SandboxProvisioningError",
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

        # 5. Retry budget guard
        if target_state == DevelopmentWorkflowState.RETRY_PREPARED:
            if not self.can_retry(current_retries, error):
                classification = self.classify_error(error) if error else "MAX_RETRIES_EXCEEDED"
                raise PolicyViolationError(
                    f"Cannot prepare retry: Budget exhausted ({current_retries}/{self.retry_policy.max_retries}) "
                    f"or error classification is non-transient ({classification})."
                )

        # 6. Required state data presence
        state_data = state_data or {}
        if target_state == DevelopmentWorkflowState.HITL_PENDING:
            if not state_data.get("candidate_hash") and not state_data.get("deliverable"):
                raise PolicyViolationError(
                    "Transition to HITL_PENDING requires candidate_hash or deliverable in state data."
                )
        elif target_state == DevelopmentWorkflowState.APPROVED:
            if not state_data.get("approval_decision"):
                raise PolicyViolationError(
                    "Transition to APPROVED requires approval_decision in state data."
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
