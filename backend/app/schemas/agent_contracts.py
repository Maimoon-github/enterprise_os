"""Bounded task grants, context requests, and evidence envelopes.

These contracts are the only interface between the Intelligence Engine and
the seven bounded worker agents. Workers never see more than what a
``TaskGrant`` and its accompanying context payload contain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
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


class ClaimValidationStatus(StrEnum):
    """Explicit verification classifications for product claims."""

    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class ClaimVerificationEntry(BaseModel):
    """Structured validation finding for an individual claim."""

    claim_id: str
    claim_text: str
    category: str = "performance"
    validation_status: ClaimValidationStatus
    confidence: float = 0.0
    evidence_references: list[str] = Field(default_factory=list)
    contradicting_evidence_references: list[str] = Field(default_factory=list)
    rule_compliance_checks: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    limitations_or_warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ClaimsDossier(BaseModel):
    """Evidence-backed claims dossier produced by W_PROD + S_VAL."""

    dossier_id: str
    tenant_id: str
    product_id: str
    claims: list[ClaimVerificationEntry] = Field(default_factory=list)
    summary_status: str = "PENDING"
    total_claims: int = 0
    supported_claims: int = 0
    rejected_claims: int = 0
    insufficient_claims: int = 0
    conflicting_claims: int = 0
    requires_review_claims: int = 0
    overall_confidence: float = 0.0
    provenance: dict[str, Any] = Field(default_factory=dict)


class ProductSpecification(BaseModel):
    """Verified product and formulation specification produced by W_PROD + S_VAL."""

    product_id: str
    product_name: str
    tenant_id: str
    formulation_id: str | None = None
    version: str = "1.0"
    normalized_attributes: dict[str, Any] = Field(default_factory=dict)
    ingredients: list[dict[str, Any]] = Field(default_factory=list)
    supporting_evidence_references: list[str] = Field(default_factory=list)
    validation_status: str = "VALIDATED"
    compliance_findings: list[str] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SentimentClassification(StrEnum):
    """Normalized sentiment categories for customer voice inputs."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class CustomerVoiceItem(BaseModel):
    """Normalized input representation of a support ticket, review, or survey response."""

    item_id: str
    source_type: str = "feedback"
    text: str
    product_id: str | None = None
    channel: str | None = None
    timestamp: datetime | None = None
    tenant_id: str | None = None
    provenance_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnonymizedSentimentVector(BaseModel):
    """Anonymized, structured sentiment and topic classification for a single customer voice item."""

    vector_id: str
    source_id_hash: str
    source_type: str = "feedback"
    tenant_id: str = "default"
    product_id: str | None = None
    channel: str | None = None
    sanitized_text: str = ""
    sentiment_label: SentimentClassification = SentimentClassification.NEUTRAL
    polarity: float = 0.0
    confidence: float = 0.0
    topics: list[str] = Field(default_factory=list)
    intent: str = "general_feedback"
    urgency: str = "low"
    detected_objections: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    praise_points: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ObjectionProfile(BaseModel):
    """Aggregated, recurring customer objection or problem profile with evidence traceability."""

    objection_id: str
    objection_type: str
    normalized_theme: str
    frequency: int = 1
    affected_products: list[str] = Field(default_factory=list)
    affected_channels: list[str] = Field(default_factory=list)
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    representative_evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    severity: str = "low"
    trend: str = "stable"
    unresolved_ambiguity: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CustomerVoiceAnalysisResult(BaseModel):
    """Consolidated customer voice deliverable produced by W_VOICE + S_PARSE."""

    analysis_id: str
    tenant_id: str
    product_id: str | None = None
    total_items_analyzed: int = 0
    average_polarity: float = 0.0
    sentiment_breakdown: dict[str, int] = Field(default_factory=dict)
    sentiment_vectors: list[AnonymizedSentimentVector] = Field(default_factory=list)
    objection_profiles: list[ObjectionProfile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    anonymization_stats: dict[str, int] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)