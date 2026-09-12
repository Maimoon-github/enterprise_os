"""Canonical Task State (CTS) lifecycle, checkpoints, dependencies, and holds."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.governance import WorkerRole


class TaskStatus(StrEnum):
    """Authoritative lifecycle states for a task under the task-state machine."""

    PENDING = "pending"
    GRANTED = "granted"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    HELD = "held"


class TaskDependency(BaseModel):
    """A directed dependency edge in the canonical task DAG."""

    upstream_task_id: str
    downstream_task_id: str


class TaskCheckpoint(BaseModel):
    """An immutable, timestamped snapshot of task progress."""

    checkpoint_id: str
    task_id: str
    status: TaskStatus
    note: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CanonicalTaskState(BaseModel):
    """The single source of truth for a task's lifecycle position."""

    task_id: str
    directive_id: str
    worker_role: WorkerRole
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[TaskDependency] = Field(default_factory=list)
    checkpoints: list[TaskCheckpoint] = Field(default_factory=list)
    hold_reason: str | None = None
    prerequisite_locks: list[str] = Field(default_factory=list)
    governance_approved: bool = True
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    failure_reason: str | None = None
    completion_criteria: list[str] = Field(default_factory=list)
    version: int = Field(default=0, ge=0, description="Optimistic-concurrency version.")


TaskState = CanonicalTaskState