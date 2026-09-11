"""Persists canonical task-state and dependency records."""
from __future__ import annotations

from app.schemas.task_state import TaskState


class TaskStateRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskState] = {}

    def upsert(self, state: TaskState) -> None:
        self._tasks[state.task_id] = state

    def get(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)
