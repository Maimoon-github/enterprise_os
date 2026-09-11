"""Bounded task grants, context requests, and evidence envelopes.

These contracts are the only interface between the Intelligence Engine and
the seven bounded worker agents. Workers never see more than what a
``TaskGrant`` and its accompanying context payload contain.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.schemas.governance import TenantScope, WorkerRole


class TaskGrant(BaseModel):
    """A bounded, time-limited authorization for a worker to act on a task."""

    task_id: str
    worker_role: WorkerRole
    tenant_scope: TenantScope
    context_ids: list[str] = Field(default_factory=list)
    expires_at: datetime


class ContextRequest(BaseModel):
    """A worker's request for policy-screened context via the Intelligence Engine."""

    task_id: str
    worker_role: WorkerRole
    query: str
    max_items: int = Field(default=10, ge=1, le=100)


class ConfidenceInterval(BaseModel):
    """A simple symmetric confidence interval around a point estimate."""

    point_estimate: float
    lower_bound: float
    upper_bound: float


class EvidenceEnvelope(BaseModel):
    """Evidence and confidence data returned by a worker after execution."""

    task_id: str
    worker_role: WorkerRole
    confidence: ConfidenceInterval
    evidence: list[str] = Field(default_factory=list)
    payload: dict[str, str] = Field(default_factory=dict)
    produced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))