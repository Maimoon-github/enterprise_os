"""CTS lifecycle, checkpoints, dependencies, holds, and state deltas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    HELD = "held"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Checkpoint(BaseModel):
    name: str
    created_at: datetime


class TaskState(BaseModel):
    task_id: str
    directive_id: str
    tenant_id: str
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    hold_reason: str | None = None
