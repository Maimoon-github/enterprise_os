"""Enforces authoritative task lifecycle transitions for the CTS."""

from __future__ import annotations

from app.core.exceptions import InvalidTransitionError
from app.schemas.task_state import CanonicalTaskState, TaskCheckpoint, TaskStatus

_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.GRANTED, TaskStatus.HELD, TaskStatus.FAILED}),
    TaskStatus.GRANTED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.HELD, TaskStatus.FAILED}),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.AWAITING_APPROVAL, TaskStatus.HELD, TaskStatus.FAILED, TaskStatus.COMPLETED}
    ),
    TaskStatus.AWAITING_APPROVAL: frozenset(
        {TaskStatus.APPROVED, TaskStatus.REJECTED, TaskStatus.HELD}
    ),
    TaskStatus.APPROVED: frozenset({TaskStatus.DISPATCHED, TaskStatus.HELD}),
    TaskStatus.REJECTED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.FAILED}),
    TaskStatus.DISPATCHED: frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED}),
    TaskStatus.HELD: frozenset(
        {
            TaskStatus.PENDING,
            TaskStatus.GRANTED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.APPROVED,
            TaskStatus.FAILED,
        }
    ),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
}


class TaskStateMachine:
    """Validates and applies transitions against ``_ALLOWED_TRANSITIONS``."""

    def legal_next_states(self, current: TaskStatus) -> frozenset[TaskStatus]:
        """Return the set of states reachable from ``current``."""

        return _ALLOWED_TRANSITIONS.get(current, frozenset())

    def transition(
        self,
        state: CanonicalTaskState,
        new_status: TaskStatus,
        checkpoint_id: str,
        note: str = "",
    ) -> CanonicalTaskState:
        """Return a new ``CanonicalTaskState`` advanced to ``new_status``.

        Raises ``InvalidTransitionError`` if the transition is not legal from
        the state's current status. The input state is never mutated in
        place; a new instance is returned to keep transitions explicit.
        """

        if new_status not in self.legal_next_states(state.status):
            raise InvalidTransitionError(
                f"Cannot transition task {state.task_id} from "
                f"{state.status.value} to {new_status.value}"
            )

        checkpoint = TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=state.task_id,
            status=new_status,
            note=note,
        )
        return state.model_copy(
            update={
                "status": new_status,
                "checkpoints": [*state.checkpoints, checkpoint],
                "version": state.version + 1,
                "hold_reason": note if new_status is TaskStatus.HELD else None,
            }
        )