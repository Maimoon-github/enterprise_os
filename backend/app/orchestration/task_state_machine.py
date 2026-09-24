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

    def can_retry(self, state: CanonicalTaskState) -> bool:
        """Return True if a failed task may be retried under resumability rules."""

        return state.status is TaskStatus.FAILED and state.retry_count < state.max_retries

    def retry(
        self,
        state: CanonicalTaskState,
        checkpoint_id: str,
        note: str = "Retrying failed task under resumability policy",
    ) -> CanonicalTaskState:
        """Advance a failed task back to PENDING if retry limits permit."""

        if not self.can_retry(state):
            raise InvalidTransitionError(
                f"Task {state.task_id} cannot be retried (status={state.status.value}, "
                f"retries={state.retry_count}/{state.max_retries})"
            )

        checkpoint = TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=state.task_id,
            status=TaskStatus.PENDING,
            note=note,
        )
        return state.model_copy(
            update={
                "status": TaskStatus.PENDING,
                "retry_count": state.retry_count + 1,
                "failure_reason": None,
                "checkpoints": [*state.checkpoints, checkpoint],
                "version": state.version + 1,
            }
        )

    def acquire_lock(
        self, state: CanonicalTaskState, lock_name: str, checkpoint_id: str, note: str = ""
    ) -> CanonicalTaskState:
        """Add a prerequisite lock to task state."""

        if lock_name in state.prerequisite_locks:
            return state

        checkpoint = TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=state.task_id,
            status=state.status,
            note=note or f"Acquired prerequisite lock '{lock_name}'",
        )
        return state.model_copy(
            update={
                "prerequisite_locks": [*state.prerequisite_locks, lock_name],
                "checkpoints": [*state.checkpoints, checkpoint],
                "version": state.version + 1,
            }
        )

    def release_lock(
        self, state: CanonicalTaskState, lock_name: str, checkpoint_id: str, note: str = ""
    ) -> CanonicalTaskState:
        """Release a prerequisite lock from task state."""

        if lock_name not in state.prerequisite_locks:
            return state

        remaining = [k for k in state.prerequisite_locks if k != lock_name]
        checkpoint = TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=state.task_id,
            status=state.status,
            note=note or f"Released prerequisite lock '{lock_name}'",
        )
        return state.model_copy(
            update={
                "prerequisite_locks": remaining,
                "checkpoints": [*state.checkpoints, checkpoint],
                "version": state.version + 1,
            }
        )

    def set_governance_approval(
        self, state: CanonicalTaskState, approved: bool, checkpoint_id: str, note: str = ""
    ) -> CanonicalTaskState:
        """Update governance approval flag with checkpoint audit."""

        checkpoint = TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=state.task_id,
            status=state.status,
            note=note or f"Governance approval set to {approved}",
        )
        return state.model_copy(
            update={
                "governance_approved": approved,
                "checkpoints": [*state.checkpoints, checkpoint],
                "version": state.version + 1,
            }
        )

    def transition(
        self,
        state: CanonicalTaskState,
        new_status: TaskStatus,
        checkpoint_id: str,
        note: str = "",
    ) -> CanonicalTaskState:
        """Return a new ``CanonicalTaskState`` advanced to ``new_status``.

        Raises ``InvalidTransitionError`` if the transition is not legal from
        the state's current status or if prerequisite locks / governance checks
        remain unresolved.
        """

        if new_status not in self.legal_next_states(state.status):
            raise InvalidTransitionError(
                f"Cannot transition task {state.task_id} from "
                f"{state.status.value} to {new_status.value}"
            )

        if new_status in (TaskStatus.GRANTED, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED):
            if state.prerequisite_locks:
                raise InvalidTransitionError(
                    f"Cannot advance task {state.task_id} to {new_status.value}: "
                    f"unresolved prerequisite locks: {sorted(state.prerequisite_locks)}"
                )
            if not state.governance_approved:
                raise InvalidTransitionError(
                    f"Cannot advance task {state.task_id} to {new_status.value}: "
                    "governance approval condition is unresolved"
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
                "failure_reason": note if new_status is TaskStatus.FAILED else state.failure_reason,
            }
        )

    def restore_checkpoint(
        self, state: CanonicalTaskState, checkpoint_id: str, new_checkpoint_id: str | None = None
    ) -> CanonicalTaskState:
        """Restore task status to a previously validated historical checkpoint."""
        for cp in reversed(state.checkpoints):
            if cp.checkpoint_id == checkpoint_id:
                if cp.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    raise InvalidTransitionError(
                        f"Cannot restore task {state.task_id} to terminal checkpoint status '{cp.status.value}'."
                    )
                recovery_cp = TaskCheckpoint(
                    checkpoint_id=new_checkpoint_id or f"recovery-{checkpoint_id}",
                    task_id=state.task_id,
                    status=cp.status,
                    note=f"Authoritative recovery to checkpoint '{checkpoint_id}' (status='{cp.status.value}')",
                )
                return state.model_copy(
                    update={
                        "status": cp.status,
                        "checkpoints": [*state.checkpoints, recovery_cp],
                        "version": state.version + 1,
                        "hold_reason": None,
                        "failure_reason": None,
                    }
                )
        raise InvalidTransitionError(
            f"Checkpoint '{checkpoint_id}' not found in task '{state.task_id}' history."
        )