"""Coordinates CTS persistence, checkpoints, locks, and exceptions."""

from __future__ import annotations

import uuid

from app.core.exceptions import InvalidTransitionError
from app.orchestration.task_state_machine import TaskStateMachine
from app.persistence.repositories.task_state import TaskStateRepository
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.provenance import ProvenanceRecorder


class TaskStateService:
    """Coordinates Canonical Task State (CTS) lifecycle, persistence, checkpoints, and recovery."""

    def __init__(
        self,
        repository: TaskStateRepository,
        state_machine: TaskStateMachine | None = None,
        provenance_recorder: ProvenanceRecorder | None = None,
        *,
        max_retries: int = 3,
    ) -> None:
        self._repository = repository
        self._state_machine = state_machine or TaskStateMachine()
        self._provenance_recorder = provenance_recorder
        self._max_retries = max_retries
        self._retry_counts: dict[str, int] = {}

    async def get_state(self, task_id: str) -> CanonicalTaskState:
        """Fetch the authoritative task state from repository."""
        return await self._repository.require(task_id)

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        """Persist state directly to repository."""
        await self._repository.save_state(tenant_id, state)

    async def transition(
        self,
        tenant_id: str,
        current_state: CanonicalTaskState,
        new_status: TaskStatus,
        *,
        note: str = "",
    ) -> CanonicalTaskState:
        """Validate transition, generate immutable checkpoint, and persist."""
        checkpoint_id = str(uuid.uuid4())
        updated = self._state_machine.transition(
            current_state, new_status, checkpoint_id=checkpoint_id, note=note
        )
        await self._repository.save_state(tenant_id, updated)
        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=tenant_id,
                entity_id=updated.task_id,
                activity=f"task_transition_{new_status.value}",
                agent="cts_state_machine",
            )
        return updated

    async def hold_task(
        self,
        tenant_id: str,
        task_id: str,
        reason: str,
    ) -> CanonicalTaskState:
        """Place task on hold with explicit reason."""
        state = await self.get_state(task_id)
        return await self.transition(tenant_id, state, TaskStatus.HELD, note=reason)

    async def resume_task(
        self,
        tenant_id: str,
        task_id: str,
        target_status: TaskStatus = TaskStatus.PENDING,
        note: str = "Resumed after hold review",
    ) -> CanonicalTaskState:
        """Resume a held task to an allowed target status."""
        state = await self.get_state(task_id)
        if state.status != TaskStatus.HELD:
            raise InvalidTransitionError(f"Task {task_id} is in status {state.status.value}, not HELD.")
        return await self.transition(tenant_id, state, target_status, note=note)

    async def handle_task_failure(
        self,
        tenant_id: str,
        task_id: str,
        error_message: str,
    ) -> CanonicalTaskState:
        """Handle execution exception by recording retry and placing on hold or failing."""
        count = self._retry_counts.get(task_id, 0) + 1
        self._retry_counts[task_id] = count
        state = await self.get_state(task_id)
        if count <= self._max_retries:
            return await self.transition(
                tenant_id,
                state,
                TaskStatus.HELD,
                note=f"Attempt {count}/{self._max_retries} failed: {error_message}. Held for review.",
            )
        return await self.transition(
            tenant_id,
            state,
            TaskStatus.FAILED,
            note=f"Max retries ({self._max_retries}) exhausted: {error_message}",
        )
