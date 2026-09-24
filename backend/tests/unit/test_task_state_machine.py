"""Verifies CTS transitions, holds, checkpoints, and DAG rules."""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidTransitionError
from app.orchestration.dag_scheduler import CyclicDependencyError, DagScheduler
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.governance import WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskDependency, TaskStatus


def test_legal_transition_advances_status_and_records_checkpoint(
    sample_task: CanonicalTaskState,
) -> None:
    machine = TaskStateMachine()

    granted = machine.transition(sample_task, TaskStatus.GRANTED, checkpoint_id="cp-1")

    assert granted.status is TaskStatus.GRANTED
    assert len(granted.checkpoints) == 1
    assert granted.checkpoints[0].status is TaskStatus.GRANTED
    assert granted.version == sample_task.version + 1
    assert sample_task.status is TaskStatus.PENDING  # original state is untouched


def test_illegal_transition_raises(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    with pytest.raises(InvalidTransitionError):
        machine.transition(sample_task, TaskStatus.DISPATCHED, checkpoint_id="cp-1")


def test_hold_records_reason_and_can_resume(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    held = machine.transition(
        sample_task, TaskStatus.HELD, checkpoint_id="cp-1", note="budget review"
    )
    assert held.hold_reason == "budget review"

    resumed = machine.transition(held, TaskStatus.PENDING, checkpoint_id="cp-2")
    assert resumed.hold_reason is None
    assert resumed.status is TaskStatus.PENDING


def test_terminal_states_have_no_legal_next_states() -> None:
    machine = TaskStateMachine()

    assert machine.legal_next_states(TaskStatus.COMPLETED) == frozenset()
    assert machine.legal_next_states(TaskStatus.FAILED) == frozenset()


def _task(task_id: str, directive_id: str, deps: list[TaskDependency]) -> CanonicalTaskState:
    return CanonicalTaskState(
        task_id=task_id,
        directive_id=directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        dependencies=deps,
    )


def test_dag_scheduler_topological_order_respects_dependencies() -> None:
    scheduler = DagScheduler()
    task_a = _task("a", "d1", [])
    task_b = _task("b", "d1", [TaskDependency(upstream_task_id="a", downstream_task_id="b")])
    task_c = _task("c", "d1", [TaskDependency(upstream_task_id="b", downstream_task_id="c")])

    order = scheduler.topological_order([task_c, task_b, task_a])

    assert order.index("a") < order.index("b") < order.index("c")


def test_dag_scheduler_detects_cycles() -> None:
    scheduler = DagScheduler()
    task_a = _task("a", "d1", [TaskDependency(upstream_task_id="b", downstream_task_id="a")])
    task_b = _task("b", "d1", [TaskDependency(upstream_task_id="a", downstream_task_id="b")])

    with pytest.raises(CyclicDependencyError):
        scheduler.topological_order([task_a, task_b])


def test_dag_scheduler_next_ready_tasks_waits_for_upstream_completion() -> None:
    scheduler = DagScheduler()
    task_a = _task("a", "d1", [])
    task_b = _task("b", "d1", [TaskDependency(upstream_task_id="a", downstream_task_id="b")])

    ready = scheduler.next_ready_tasks([task_a, task_b])
    assert [task.task_id for task in ready] == ["a"]

    completed_a = task_a.model_copy(update={"status": TaskStatus.COMPLETED})
    ready_after_completion = scheduler.next_ready_tasks([completed_a, task_b])
    assert [task.task_id for task in ready_after_completion] == ["b"]


def test_prerequisite_locks_block_progression(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    locked = machine.acquire_lock(sample_task, "legal_signoff", checkpoint_id="cp-lock-1")
    assert "legal_signoff" in locked.prerequisite_locks

    # Granted is blocked while locked
    with pytest.raises(InvalidTransitionError) as exc_info:
        machine.transition(locked, TaskStatus.GRANTED, checkpoint_id="cp-2")
    assert "unresolved prerequisite locks" in str(exc_info.value).lower()

    # Releasing lock allows transition
    unlocked = machine.release_lock(locked, "legal_signoff", checkpoint_id="cp-unlock-1")
    assert "legal_signoff" not in unlocked.prerequisite_locks

    granted = machine.transition(unlocked, TaskStatus.GRANTED, checkpoint_id="cp-3")
    assert granted.status is TaskStatus.GRANTED


def test_governance_approval_blocks_progression(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    unapproved = machine.set_governance_approval(sample_task, False, checkpoint_id="cp-gov-1")
    assert unapproved.governance_approved is False

    with pytest.raises(InvalidTransitionError) as exc_info:
        machine.transition(unapproved, TaskStatus.GRANTED, checkpoint_id="cp-2")
    assert "governance approval condition is unresolved" in str(exc_info.value).lower()

    approved = machine.set_governance_approval(unapproved, True, checkpoint_id="cp-gov-2")
    assert approved.governance_approved is True
    granted = machine.transition(approved, TaskStatus.GRANTED, checkpoint_id="cp-3")
    assert granted.status is TaskStatus.GRANTED


def test_task_retries_and_resumability(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    # Move to FAILED
    failed = machine.transition(
        sample_task, TaskStatus.FAILED, checkpoint_id="cp-f1", note="transient network timeout"
    )
    assert failed.status is TaskStatus.FAILED
    assert failed.failure_reason == "transient network timeout"
    assert machine.can_retry(failed) is True

    # Retry 1
    retried_1 = machine.retry(failed, checkpoint_id="cp-r1")
    assert retried_1.status is TaskStatus.PENDING
    assert retried_1.retry_count == 1
    assert retried_1.failure_reason is None

    # Fail again and exhaust max_retries (simulate reaching limit)
    exhausted = retried_1.model_copy(
        update={"status": TaskStatus.FAILED, "retry_count": retried_1.max_retries}
    )
    assert machine.can_retry(exhausted) is False
    with pytest.raises(InvalidTransitionError):
        machine.retry(exhausted, checkpoint_id="cp-fail-exhausted")


def test_dag_scheduler_blocks_locked_and_unapproved_tasks() -> None:
    scheduler = DagScheduler()
    task_normal = _task("normal", "d1", [])
    task_locked = _task("locked", "d1", []).model_copy(update={"prerequisite_locks": ["compliance_hold"]})
    task_unapproved = _task("unapproved", "d1", []).model_copy(update={"governance_approved": False})

    ready = scheduler.next_ready_tasks([task_normal, task_locked, task_unapproved])
    assert [t.task_id for t in ready] == ["normal"]

    reasons_locked = scheduler.unresolved_reasons(task_locked, [task_normal, task_locked])
    assert any("prerequisite locks" in r.lower() for r in reasons_locked)

    reasons_unapproved = scheduler.unresolved_reasons(task_unapproved, [task_normal, task_unapproved])
    assert any("governance authorization" in r.lower() for r in reasons_unapproved)


def test_task_state_machine_restore_checkpoint(sample_task: CanonicalTaskState) -> None:
    machine = TaskStateMachine()

    # PENDING -> GRANTED -> IN_PROGRESS -> HELD
    t_granted = machine.transition(sample_task, TaskStatus.GRANTED, checkpoint_id="cp-1")
    t_in_prog = machine.transition(t_granted, TaskStatus.IN_PROGRESS, checkpoint_id="cp-2")
    t_held = machine.transition(t_in_prog, TaskStatus.HELD, checkpoint_id="cp-3", note="Hold for audit")
    assert t_held.status is TaskStatus.HELD
    assert t_held.version == 3

    # Restore to cp-2 (IN_PROGRESS)
    restored = machine.restore_checkpoint(t_held, checkpoint_id="cp-2")
    assert restored.status is TaskStatus.IN_PROGRESS
    assert restored.version == 4
    assert restored.hold_reason is None

    # Rejection for non-existent checkpoint
    with pytest.raises(InvalidTransitionError, match="not found"):
        machine.restore_checkpoint(restored, checkpoint_id="cp-nonexistent")

    # Rejection when restoring to terminal checkpoint status
    t_failed = machine.transition(restored, TaskStatus.FAILED, checkpoint_id="cp-fail")
    with pytest.raises(InvalidTransitionError, match="terminal checkpoint status"):
        machine.restore_checkpoint(t_failed, checkpoint_id="cp-fail")