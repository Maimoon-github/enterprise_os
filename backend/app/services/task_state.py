"""Coordinates CTS persistence, checkpoints, locks, and exceptions."""
from __future__ import annotations

from app.schemas.task_state import TaskState


class TaskStateService:
    def __init__(self) -> None:
        self._store: dict[str, TaskState] = {}

    def get(self, task_id: str) -> TaskState | None:
        return self._store.get(task_id)

    def put(self, state: TaskState) -> None:
        self._store[state.task_id] = state
