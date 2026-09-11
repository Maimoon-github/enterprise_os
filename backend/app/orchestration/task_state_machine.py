"""Enforces authoritative task lifecycle transitions."""
from __future__ import annotations

from app.schemas.task_state import TaskState, TaskStatus

_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.HELD},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.HELD: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskStateMachine:
    def transition(self, state: TaskState, target: TaskStatus) -> TaskState:
        if target not in _ALLOWED[state.status]:
            raise ValueError(f"illegal transition {state.status} -> {target}")
        return state.model_copy(update={"status": target})
