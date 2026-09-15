"""Focused unit and integration tests for Task DE-02: Sequential State Machine (W_DEV).

Validates:
1. Strict sequential progression through canonical development workflow states.
2. Hard-enforcement of max_concurrency=1 (single active sub-agent invariant).
3. Exclusive development execution leases: acquisition, contention, renewal, expiry, release.
4. Transition guards: predecessor validation, lease ownership, unexpired grants, required data.
5. Error classification and bounded retries for transient failures.
6. Idempotent checkpointing and replay-safe deduplication.
7. Restart-safe state recovery from durable checkpoints.
8. DagScheduler serialization of concurrent development tasks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.core.exceptions import InvalidTransitionError, PolicyViolationError
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.task_state import (
    CanonicalTaskState,
    DevelopmentExecutionLease,
    DevelopmentWorkflowCheckpoint,
    DevelopmentWorkflowState,
    RetryClassification,
    TaskStatus,
    WorkflowRetryPolicy,
)
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


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
def task_state_service() -> TaskStateService:
    repo = FakeTaskStateRepository()
    return TaskStateService(repository=repo, provenance_recorder=None)


@pytest.fixture
def active_lease() -> DevelopmentExecutionLease:
    return DevelopmentExecutionLease(
        workflow_id="wf-100",
        task_id="task-100",
        step_id="step-dev-code",
        attempt_id="att-1",
        owner_id="worker-w-dev-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


# ===========================================================================
# 1. Sequential Progression & Lifecycle Tests
# ===========================================================================

def test_valid_forward_lifecycle_progression(
    state_machine: DevelopmentStateMachine, active_lease: DevelopmentExecutionLease
) -> None:
    """W_DEV moves strictly forward through declared lifecycle states."""
    task_id = "task-seq-001"
    wf_id = "wf-seq-001"

    # RECEIVED -> POLICY_BOUND
    cp1 = state_machine.transition(
        current_state=DevelopmentWorkflowState.RECEIVED,
        target_state=DevelopmentWorkflowState.POLICY_BOUND,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-0",
        attempt_id="att-1",
        idempotency_key="key-1",
    )
    assert cp1.state == DevelopmentWorkflowState.POLICY_BOUND

    # POLICY_BOUND -> PLANNING
    cp2 = state_machine.transition(
        current_state=DevelopmentWorkflowState.POLICY_BOUND,
        target_state=DevelopmentWorkflowState.PLANNING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-plan",
        attempt_id="att-1",
        idempotency_key="key-2",
    )
    assert cp2.state == DevelopmentWorkflowState.PLANNING

    # PLANNING -> RESULT_SEALED
    cp3 = state_machine.transition(
        current_state=DevelopmentWorkflowState.PLANNING,
        target_state=DevelopmentWorkflowState.RESULT_SEALED,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-plan",
        attempt_id="att-1",
        idempotency_key="key-3",
        lease=active_lease,
        expected_owner="worker-w-dev-1",
    )
    assert cp3.state == DevelopmentWorkflowState.RESULT_SEALED

    # RESULT_SEALED -> HITL_PENDING (requires candidate_hash)
    cp4 = state_machine.transition(
        current_state=DevelopmentWorkflowState.RESULT_SEALED,
        target_state=DevelopmentWorkflowState.HITL_PENDING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-plan",
        attempt_id="att-1",
        idempotency_key="key-4",
        state_data={"candidate_hash": "sha256:abc1234567890abcdef"},
    )
    assert cp4.state == DevelopmentWorkflowState.HITL_PENDING

    # HITL_PENDING -> APPROVED (requires approval_decision)
    cp5 = state_machine.transition(
        current_state=DevelopmentWorkflowState.HITL_PENDING,
        target_state=DevelopmentWorkflowState.APPROVED,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-plan",
        attempt_id="att-1",
        idempotency_key="key-5",
        state_data={"approval_decision": "APPROVE"},
    )
    assert cp5.state == DevelopmentWorkflowState.APPROVED

    # APPROVED -> SANDBOX_PROVISIONING
    cp6 = state_machine.transition(
        current_state=DevelopmentWorkflowState.APPROVED,
        target_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-code",
        attempt_id="att-1",
        idempotency_key="key-6",
    )
    assert cp6.state == DevelopmentWorkflowState.SANDBOX_PROVISIONING

    # SANDBOX_PROVISIONING -> SUBAGENT_RUNNING (requires lease and concurrency=1)
    cp7 = state_machine.transition(
        current_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-code",
        attempt_id="att-1",
        idempotency_key="key-7",
        lease=active_lease,
        expected_owner="worker-w-dev-1",
        active_subagent_count=0,
        active_subagent="DEV-CODE",
    )
    assert cp7.state == DevelopmentWorkflowState.SUBAGENT_RUNNING
    assert cp7.active_subagent == "DEV-CODE"

    # SUBAGENT_RUNNING -> RESULT_SEALED
    cp8 = state_machine.transition(
        current_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
        target_state=DevelopmentWorkflowState.RESULT_SEALED,
        task_id=task_id,
        workflow_id=wf_id,
        step_id="step-code",
        attempt_id="att-1",
        idempotency_key="key-8",
        lease=active_lease,
        expected_owner="worker-w-dev-1",
    )
    assert cp8.state == DevelopmentWorkflowState.RESULT_SEALED


# ===========================================================================
# 2. Max Concurrency = 1 Enforcement Tests
# ===========================================================================

def test_max_concurrency_violation_rejected(
    state_machine: DevelopmentStateMachine, active_lease: DevelopmentExecutionLease
) -> None:
    """Transitioning to SUBAGENT_RUNNING fails closed if an active sub-agent is already running."""
    with pytest.raises(PolicyViolationError, match="Max concurrency violation"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
            task_id="task-conc",
            workflow_id="wf-conc",
            step_id="step-2",
            attempt_id="att-1",
            idempotency_key="key-conc",
            lease=active_lease,
            expected_owner="worker-w-dev-1",
            active_subagent_count=1,  # Concurrency breach!
        )


def test_dag_scheduler_serializes_development_tasks() -> None:
    """DagScheduler.enforce_development_concurrency limits ready development tasks to 1."""
    scheduler = DagScheduler()

    tasks = [
        CanonicalTaskState(
            task_id="t-dev-1",
            directive_id="dir-1",
            worker_role=WorkerRole.DEVELOPMENT,
            status=TaskStatus.PENDING,
            governance_approved=True,
        ),
        CanonicalTaskState(
            task_id="t-strat-1",
            directive_id="dir-1",
            worker_role=WorkerRole.STRATEGY,
            status=TaskStatus.PENDING,
            governance_approved=True,
        ),
        CanonicalTaskState(
            task_id="t-dev-2",
            directive_id="dir-1",
            worker_role=WorkerRole.DEVELOPMENT,
            status=TaskStatus.PENDING,
            governance_approved=True,
        ),
    ]

    filtered = scheduler.enforce_development_concurrency(tasks)
    dev_tasks = [t for t in filtered if t.worker_role == WorkerRole.DEVELOPMENT]
    assert len(dev_tasks) == 1
    assert dev_tasks[0].task_id == "t-dev-1"
    assert len(filtered) == 2  # t-dev-1 + t-strat-1; t-dev-2 is deferred


# ===========================================================================
# 3. Development Execution Lease Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_lease_acquisition_contention_and_release(
    task_state_service: TaskStateService,
) -> None:
    """Exclusive leases prevent competing owners from concurrently executing a task."""
    task_id = "task-lease-01"

    # 1. Acquire lease
    lease1 = await task_state_service.acquire_development_lease(
        task_id=task_id,
        workflow_id="wf-1",
        step_id="step-1",
        attempt_id="att-1",
        owner_id="worker-A",
        ttl_seconds=30,
    )
    assert lease1.owner_id == "worker-A"
    assert not lease1.is_expired()

    # 2. Competing worker fails closed
    with pytest.raises(PolicyViolationError, match="Lease contention"):
        await task_state_service.acquire_development_lease(
            task_id=task_id,
            workflow_id="wf-1",
            step_id="step-1",
            attempt_id="att-1",
            owner_id="worker-B",
            ttl_seconds=30,
        )

    # 3. Same owner can renew / extend
    renewed = await task_state_service.renew_development_lease(
        task_id=task_id,
        lease_id=lease1.lease_id,
        owner_id="worker-A",
        ttl_seconds=60,
    )
    assert renewed.version == lease1.version + 1

    # 4. Release lease
    await task_state_service.release_development_lease(
        task_id=task_id,
        lease_id=lease1.lease_id,
        owner_id="worker-A",
    )

    # 5. Worker B can now acquire
    lease2 = await task_state_service.acquire_development_lease(
        task_id=task_id,
        workflow_id="wf-1",
        step_id="step-1",
        attempt_id="att-1",
        owner_id="worker-B",
        ttl_seconds=30,
    )
    assert lease2.owner_id == "worker-B"


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over(
    task_state_service: TaskStateService,
) -> None:
    """An expired lease can be acquired by a new worker."""
    task_id = "task-exp-lease"

    # Acquire lease with 0-second TTL
    expired_lease = await task_state_service.acquire_development_lease(
        task_id=task_id,
        workflow_id="wf-exp",
        step_id="step-1",
        attempt_id="att-1",
        owner_id="worker-old",
        ttl_seconds=-5,  # immediately expired in the past
    )
    assert expired_lease.is_expired()

    # New owner can take over expired lease
    new_lease = await task_state_service.acquire_development_lease(
        task_id=task_id,
        workflow_id="wf-exp",
        step_id="step-1",
        attempt_id="att-1",
        owner_id="worker-new",
        ttl_seconds=60,
    )
    assert new_lease.owner_id == "worker-new"
    assert not new_lease.is_expired()


# ===========================================================================
# 4. Transition Guards & Invalid States
# ===========================================================================

def test_invalid_state_transition_fails_closed(
    state_machine: DevelopmentStateMachine,
) -> None:
    """Skipping required states (e.g. RECEIVED -> COMPLETED directly) is rejected."""
    with pytest.raises(InvalidTransitionError, match="Illegal transition"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.RECEIVED,
            target_state=DevelopmentWorkflowState.COMPLETED,
            task_id="t1",
            workflow_id="w1",
            step_id="s1",
            attempt_id="a1",
            idempotency_key="k1",
        )


def test_subagent_running_requires_lease(
    state_machine: DevelopmentStateMachine,
) -> None:
    """Entering SUBAGENT_RUNNING without a valid lease fails closed."""
    with pytest.raises(PolicyViolationError, match="Execution lease is required"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
            task_id="t1",
            workflow_id="w1",
            step_id="s1",
            attempt_id="a1",
            idempotency_key="k1",
            lease=None,
        )


def test_expired_grant_rejected_at_transition(
    state_machine: DevelopmentStateMachine, active_lease: DevelopmentExecutionLease
) -> None:
    """State transition fails closed if task grant is expired."""
    with pytest.raises(PolicyViolationError, match="grant has expired"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
            target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
            task_id="t1",
            workflow_id="w1",
            step_id="s1",
            attempt_id="a1",
            idempotency_key="k1",
            lease=active_lease,
            expected_owner="worker-w-dev-1",
            grant_expired=True,
        )


def test_hitl_pending_requires_candidate_hash(
    state_machine: DevelopmentStateMachine,
) -> None:
    """Transitioning to HITL_PENDING without candidate hash or deliverable fails closed."""
    with pytest.raises(PolicyViolationError, match="requires candidate_hash or deliverable"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.RESULT_SEALED,
            target_state=DevelopmentWorkflowState.HITL_PENDING,
            task_id="t1",
            workflow_id="w1",
            step_id="s1",
            attempt_id="a1",
            idempotency_key="k1",
            state_data={},  # missing candidate hash
        )


# ===========================================================================
# 5. Error Classification & Bounded Retries
# ===========================================================================

def test_transient_error_classification_and_retry_budget(
    state_machine: DevelopmentStateMachine,
) -> None:
    """Transient failures are retryable up to max_retries limit."""
    assert state_machine.classify_error("TimeoutError") == RetryClassification.TRANSIENT
    assert state_machine.classify_error("LeaseContentionError") == RetryClassification.TRANSIENT
    assert state_machine.classify_error("Path traversal detected") == RetryClassification.SECURITY_BLOCK
    assert state_machine.classify_error("UnrecoverableSyntaxError") == RetryClassification.PERMANENT

    # Retry within budget
    assert state_machine.can_retry(current_retries=0, error="TimeoutError") is True
    assert state_machine.can_retry(current_retries=2, error="TimeoutError") is True

    # Retry budget exhausted
    assert state_machine.can_retry(current_retries=3, error="TimeoutError") is False

    # Non-transient error not retryable
    assert state_machine.can_retry(current_retries=0, error="SecurityPolicyError") is False


def test_retry_budget_exhaustion_rejects_retry_prepared(
    state_machine: DevelopmentStateMachine,
) -> None:
    """Exhausted retries prevent transition to RETRY_PREPARED."""
    with pytest.raises(PolicyViolationError, match="Cannot prepare retry: Budget exhausted"):
        state_machine.transition(
            current_state=DevelopmentWorkflowState.CORRECTION_REQUIRED,
            target_state=DevelopmentWorkflowState.RETRY_PREPARED,
            task_id="t-retry",
            workflow_id="wf-retry",
            step_id="step-1",
            attempt_id="att-1",
            idempotency_key="key-retry-fail",
            current_retries=3,  # Max retries reached
            error="TimeoutError",
        )


# ===========================================================================
# 6. Checkpointing, Idempotency & Restart Recovery
# ===========================================================================

@pytest.mark.asyncio
async def test_idempotent_checkpointing(
    task_state_service: TaskStateService,
) -> None:
    """Duplicate replay with same idempotency key returns committed checkpoint without side-effects."""
    cp = DevelopmentWorkflowCheckpoint(
        task_id="task-idem-01",
        workflow_id="wf-idem",
        step_id="step-1",
        attempt_id="att-1",
        state=DevelopmentWorkflowState.RECEIVED,
        idempotency_key="idempotency-token-xyz",
        state_data={"payload": "initial"},
    )

    first = await task_state_service.save_development_checkpoint("tenant-1", cp)
    second = await task_state_service.save_development_checkpoint("tenant-1", cp)

    assert first.checkpoint_id == second.checkpoint_id
    history = task_state_service._dev_checkpoints.get("task-idem-01", [])
    assert len(history) == 1  # Deduplicated


@pytest.mark.asyncio
async def test_restart_safe_workflow_resume(
    task_state_service: TaskStateService,
) -> None:
    """Service restart safely resumes from latest durable checkpoint."""
    task_id = "task-restart-01"

    # Simulate workflow progressing to APPROVED before crash
    cp = DevelopmentWorkflowCheckpoint(
        task_id=task_id,
        workflow_id="wf-restart",
        step_id="step-plan",
        attempt_id="att-1",
        state=DevelopmentWorkflowState.APPROVED,
        idempotency_key="idem-key-approved",
        state_data={"plan_hash": "sha256:plan999", "approval_decision": "APPROVE"},
    )
    await task_state_service.save_development_checkpoint("tenant-1", cp)

    # Simulate restart by reading from persistence
    resumed_cp, state_data = await task_state_service.resume_development_workflow(
        "tenant-1", task_id
    )

    assert resumed_cp.state == DevelopmentWorkflowState.APPROVED
    assert state_data["plan_hash"] == "sha256:plan999"
    assert resumed_cp.checkpoint_id == cp.checkpoint_id
