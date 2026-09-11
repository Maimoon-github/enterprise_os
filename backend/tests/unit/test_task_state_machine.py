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