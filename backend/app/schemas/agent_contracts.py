"""Bounded task grants, context requests, and evidence envelopes.

These contracts are the only interface between the Intelligence Engine and
the seven bounded worker agents. Workers never see more than what a
``TaskGrant`` and its accompanying context payload contain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.governance import RiskLevel, TenantScope, WorkerRole


class TaskGrant(BaseModel):
    """A bounded, time-limited authorization for a worker to act on a task."""

    task_id: str
    worker_role: WorkerRole
    tenant_scope: TenantScope
    brand_id: str = "default"
    objective: str = ""
    task_scope: str = ""
    task_slice: str = ""
    cts_state: dict[str, Any] = Field(default_factory=dict)
    brand_rules: dict[str, Any] = Field(default_factory=dict)
    validated_evidence: list[dict[str, Any]] = Field(default_factory=list)
    provenance_references: list[str] = Field(default_factory=list)
    freshness_metadata: dict[str, Any] = Field(default_factory=dict)
    policy_constraints: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    expires_at: datetime
    tool_permissions: list[str] = Field(default_factory=list)
    sandbox_capabilities: list[str] = Field(default_factory=list)
    token_budget: int = 10000
    budget_breakdown: dict[str, int] = Field(default_factory=dict)
    risk_tier: RiskLevel = RiskLevel.LOW
    stop_conditions: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)


class ContextRequest(BaseModel):
    """A worker's request for policy-screened context via the Intelligence Engine."""

    task_id: str
    worker_role: WorkerRole
    query: str
    brand_id: str = "default"
    purpose: str = ""
    freshness_target: timedelta | None = None
    provenance_required: bool = True
    max_items: int = Field(default=10, ge=1, le=100)
    max_tokens: int = Field(default=4000, ge=100, le=32000)


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
    findings: list[str] = Field(default_factory=list)
    generated_artifacts: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    proposed_state_changes: dict[str, str] = Field(default_factory=dict)
    unresolved_risks_or_assumptions: list[str] = Field(default_factory=list)