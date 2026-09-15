"""Canonical Task State (CTS) lifecycle, checkpoints, dependencies, and holds."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

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
    cts_state: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=0, ge=0, description="Optimistic-concurrency version.")


TaskState = CanonicalTaskState


class MilestoneStatus(StrEnum):
    """Authoritative milestone evaluation status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class MilestoneCheckpoint(BaseModel):
    """Immutable checkpoint evaluating an architectural milestone over linked tasks."""

    milestone_id: str
    title: str = ""
    status: MilestoneStatus
    tenant_id: str
    linked_task_ids: list[str] = Field(default_factory=list)
    evidence_package_id: str | None = None
    dossier_id: str | None = None
    clearance_ids: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    blockers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StakeholderSignOff(BaseModel):
    """Explicit sign-off by Brand Stakeholder / Portfolio Owner required for T34 and M7 project closeout."""

    stakeholder_id: str
    stakeholder_role: str = "Brand Stakeholder / Portfolio Owner"
    decision: str = "APPROVED"  # "APPROVED" | "REJECTED"
    signature: str | None = None
    signed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""


class ProjectCloseoutDossier(BaseModel):
    """Authoritative dossier summarizing final system verification and project closeout (T34)."""

    closeout_id: str
    tenant_id: str
    brand_id: str = "default"
    milestone_m7_status: MilestoneStatus
    project_status: str  # "CLOSED" | "NOT_CLOSED" | "BLOCKED" | "FAILED"
    t32_learning_status: str
    t33_audit_status: str
    model_a_verified: bool = True
    sandbox_coverage_verified: bool = True
    governance_verified: bool = True
    ephemeral_boundaries_verified: bool = True
    stakeholder_approved: bool = False
    blockers: list[str] = Field(default_factory=list)
    closed_at: datetime | None = None


# ===========================================================================
# Development Engine Workflow & Lease Schemas (DE-02)
# ===========================================================================

class DevelopmentWorkflowState(StrEnum):
    """Canonical lifecycle states for W_DEV internal sequential state machine."""

    RECEIVED = "RECEIVED"
    POLICY_BOUND = "POLICY_BOUND"
    PLANNING = "PLANNING"
    RESULT_SEALED = "RESULT_SEALED"
    HITL_PENDING = "HITL_PENDING"
    APPROVED = "APPROVED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    RETRY_PREPARED = "RETRY_PREPARED"
    SANDBOX_PROVISIONING = "SANDBOX_PROVISIONING"
    VALIDATED = "VALIDATED"
    SUBAGENT_RUNNING = "SUBAGENT_RUNNING"
    NEXT_STEP = "NEXT_STEP"
    RELEASE_READY = "RELEASE_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class DevelopmentExecutionLease(BaseModel):
    """Durable execution lease enforcing single-active-subagent execution (max_concurrency=1)."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    task_id: str
    step_id: str
    attempt_id: str
    owner_id: str
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    version: int = Field(default=1, ge=1)

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True if lease has expired."""
        current_time = now or datetime.now(UTC)
        exp_utc = (
            self.expires_at
            if self.expires_at.tzinfo is not None
            else self.expires_at.replace(tzinfo=UTC)
        )
        return exp_utc <= current_time


class DevelopmentWorkflowCheckpoint(BaseModel):
    """Durable state checkpoint persisted after each successful state transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    workflow_id: str
    step_id: str
    attempt_id: str
    state: DevelopmentWorkflowState
    idempotency_key: str
    state_data: dict[str, Any] = Field(default_factory=dict)
    active_subagent: str | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetryClassification(StrEnum):
    """Explicit classification of failure types for bounded retry eligibility."""

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    HITL_REJECTION = "HITL_REJECTION"


class WorkflowRetryPolicy(BaseModel):
    """Deterministic policy controlling bounded retries on transient failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    retryable_errors: list[str] = Field(
        default_factory=lambda: [
            "TransientWorkflowError",
            "TimeoutError",
            "LeaseContentionError",
            "SandboxProvisioningError",
            "SandboxValidationError",
            "SandboxIsolationError",
            "SandboxExecutionError",
        ]
    )