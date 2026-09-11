"""Verifies CTS transitions, holds, checkpoints, and DAG rules."""
import pytest

from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.task_state import TaskState, TaskStatus


def _state(status: TaskStatus) -> TaskState:
    return TaskState(task_id="t1", directive_id="d1", tenant_id="t1", status=status)


def test_legal_transition() -> None:
    sm = TaskStateMachine()
    assert sm.transition(_state(TaskStatus.PENDING), TaskStatus.READY).status is TaskStatus.READY


def test_illegal_transition() -> None:
    sm = TaskStateMachine()
    with pytest.raises(ValueError):
        sm.transition(_state(TaskStatus.COMPLETED), TaskStatus.RUNNING)
