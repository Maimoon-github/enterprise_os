"""Bounded task grants, context requests, and evidence envelopes.

These contracts are the only interface between the Intelligence Engine and
the seven bounded worker agents. Workers never see more than what a
``TaskGrant`` and its accompanying context payload contain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
import uuid

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


class ChannelAllocation(BaseModel):
    """Media and channel-specific budget allocation produced by W_STRAT + S_ALLOC."""

    channel: str
    allocated_amount: float
    percentage_of_total: float
    role: str = ""
    primary_kpi: str = "Blended ROAS"
    prior_roas: float | None = None
    target_roas_range: tuple[float, float] | None = None
    constraints: list[str] = Field(default_factory=list)


class FunnelStageAllocation(BaseModel):
    """Full-funnel stage distribution and conversion hypotheses."""

    stage: str
    stage_name: str
    allocated_amount: float
    percentage_of_total: float
    channels: list[str] = Field(default_factory=list)
    objective: str = ""
    transition_hypothesis: str = ""
    target_metrics: dict[str, str] = Field(default_factory=dict)


class StrategyScenario(BaseModel):
    """Alternative marketing mix scenario comparison model."""

    scenario_id: str
    scenario_name: str
    description: str = ""
    is_recommended: bool = False
    allocations_by_channel: dict[str, float] = Field(default_factory=dict)
    allocations_by_stage: dict[str, float] = Field(default_factory=dict)
    expected_blended_roas: float = 0.0
    risk_level: str = "medium"
    key_assumptions: list[str] = Field(default_factory=list)


class OmnichannelStrategyPlan(BaseModel):
    """Consolidated omnichannel marketing roadmap and budget allocation proposal produced by W_STRAT + S_ALLOC."""

    plan_id: str
    tenant_id: str
    brand_id: str
    time_horizon: str = "90_days"
    budget_ceiling: float
    total_allocated: float
    unallocated_contingency: float = 0.0
    channel_allocations: list[ChannelAllocation] = Field(default_factory=list)
    funnel_stages: list[FunnelStageAllocation] = Field(default_factory=list)
    scenarios: list[StrategyScenario] = Field(default_factory=list)
    recommended_scenario: str = "balanced"
    approved_claims_applied: list[str] = Field(default_factory=list)
    objections_addressed: list[str] = Field(default_factory=list)
    competitor_signals_factored: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    unsupported_estimates_or_caveats: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceInterval | None = None


class AdCopyVariant(BaseModel):
    """Channel-specific ad copy draft produced by W_CREAT + S_COPY."""

    variant_id: str
    channel: str
    format: str = "feed_ad"
    headline: str
    hook_angle: str = "pain_point"
    hook_score: float = 0.85
    body_copy: str
    cta: str = "Learn More"
    cta_variants: list[str] = Field(default_factory=list)
    audience_segment: str = "all"
    funnel_stage: str = "TOFU"
    source_claim_ids: list[str] = Field(default_factory=list)
    character_count: int = 0
    compliance_checked: bool = True
    disclaimers: list[str] = Field(default_factory=list)


class VisualBrief(BaseModel):
    """Structured visual direction brief for creative asset production."""

    brief_id: str
    asset_title: str
    channel: str
    format: str = "1:1_feed"
    aspect_ratio: str = "1:1"
    art_direction: str = ""
    imagery_description: str = ""
    text_overlay: str = ""
    color_palette_guidance: list[str] = Field(default_factory=list)
    required_elements: list[str] = Field(default_factory=list)
    prohibited_elements: list[str] = Field(default_factory=list)


class SocialPostVariant(BaseModel):
    """Platform-adapted organic or sponsored social post draft."""

    post_id: str
    platform: str
    post_type: str = "post"
    hook: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    call_to_action: str = ""
    source_claim_ids: list[str] = Field(default_factory=list)
    character_limit: int = 2200
    is_within_limits: bool = True


class ContentScheduleItem(BaseModel):
    """Channel and content release calendar slot aligned with marketing strategy."""

    schedule_id: str
    day_or_week: str
    channel: str
    funnel_stage: str = "TOFU"
    format: str = "feed_ad"
    variant_ref: str
    primary_objective: str
    target_audience: str = ""
    cadence_notes: str = ""


class CreativePackage(BaseModel):
    """Consolidated creative deliverable produced by W_CREAT + S_COPY."""

    package_id: str
    tenant_id: str
    brand_id: str
    objective: str
    target_audience: str = ""
    funnel_stage: str = "full_funnel"
    ad_copy_variants: list[AdCopyVariant] = Field(default_factory=list)
    social_posts: list[SocialPostVariant] = Field(default_factory=list)
    visual_briefs: list[VisualBrief] = Field(default_factory=list)
    schedules: list[ContentScheduleItem] = Field(default_factory=list)
    approved_claim_refs: list[str] = Field(default_factory=list)
    flagged_unsupported_claims: list[str] = Field(default_factory=list)
    compliance_warnings: list[str] = Field(default_factory=list)
    persona_voice: str = "authoritative"
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceInterval | None = None


class ResponsiveBreakpoint(BaseModel):
    """Layout and responsive styling constraints for a device viewport category."""

    breakpoint: str = "mobile"
    min_width: int | None = None
    max_width: int | None = None
    layout_rules: dict[str, str] = Field(default_factory=dict)


class UITemplateDefinition(BaseModel):
    """Responsive UI template and component definition produced by W_DEV + S_CODE."""

    template_id: str
    name: str
    component_type: str = "component"
    template_markup: str
    css_styles: str = ""
    responsive_breakpoints: list[ResponsiveBreakpoint] = Field(default_factory=list)
    design_tokens: dict[str, str] = Field(default_factory=dict)
    props_schema: dict[str, Any] = Field(default_factory=dict)
    is_responsive_validated: bool = True


class CmsSchemaDiff(BaseModel):
    """Structured diff representing schema extensions or modifications for CMS models."""

    schema_name: str
    target_content_type: str = "pages"
    operation: str = "extend_fields"
    added_fields: list[dict[str, Any]] = Field(default_factory=list)
    modified_fields: list[dict[str, Any]] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    is_backward_compatible: bool = True


class CodeDiffEntry(BaseModel):
    """Structured unified code diff entry for an individual file."""

    file_path: str
    action: str = "modify"
    diff_unified: str
    ast_validated: bool = True
    syntax_lint_passed: bool = True
    syntax_errors: list[str] = Field(default_factory=list)
    scope_boundary_verified: bool = True


class DevelopmentDeliverable(BaseModel):
    """Consolidated engineering deliverable produced by W_DEV + S_CODE."""

    deliverable_id: str
    tenant_id: str
    task_id: str
    component_name: str
    ui_templates: list[UITemplateDefinition] = Field(default_factory=list)
    cms_schema_diffs: list[CmsSchemaDiff] = Field(default_factory=list)
    code_diffs: list[CodeDiffEntry] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    validation_findings: list[str] = Field(default_factory=list)
    security_checks_passed: bool = True
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceInterval | None = None


class ConflictSeverity(StrEnum):
    """Classification of cross-envelope contradiction severity."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class EvidenceConflict(BaseModel):
    """Structured record of a cross-envelope contradiction or mismatch."""

    conflict_id: str
    conflict_type: str
    severity: ConflictSeverity = ConflictSeverity.WARNING
    conflicting_task_ids: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    description: str
    field_or_topic: str = ""
    resolvable_by_hitl: bool = True


class RejectedEvidenceItem(BaseModel):
    """Trackable record of an evidence envelope or finding rejected during consolidation."""

    task_id: str
    worker_role: str
    rejection_reason: str
    rejection_code: str
    raw_evidence_summary: str = ""
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CandidateStateDelta(BaseModel):
    """Validated candidate task or entity state change proposed for CTS adoption."""

    task_id: str
    tenant_id: str
    worker_role: WorkerRole | str
    target_status: str
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    is_authorized: bool = True
    validation_notes: str = ""


class ConsolidatedConfidenceSummary(BaseModel):
    """Statistical summary of confidence across consolidated worker evidence."""

    weighted_point_estimate: float
    lower_bound: float
    upper_bound: float
    dispersion: float = 0.0
    confidence_band: str = "MODERATE"
    is_statistically_sound: bool = True
    envelope_count: int = 0


class ConsolidatedPackageStatus(StrEnum):
    """Authoritative status of a consolidated evidence package."""

    VALID = "VALID"
    FLAGGED_WITH_CONFLICTS = "FLAGGED_WITH_CONFLICTS"
    REJECTED = "REJECTED"


class ConsolidatedEvidencePackage(BaseModel):
    """Consolidated, verified evidence package assembled by the Intelligence Engine."""

    package_id: str
    tenant_id: str
    status: ConsolidatedPackageStatus = ConsolidatedPackageStatus.VALID
    source_task_ids: list[str] = Field(default_factory=list)
    participating_roles: list[WorkerRole] = Field(default_factory=list)
    validated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    confidence_summary: ConsolidatedConfidenceSummary
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rejected_items: list[RejectedEvidenceItem] = Field(default_factory=list)
    proposed_state_deltas: list[CandidateStateDelta] = Field(default_factory=list)
    synthesized_evidence_summary: list[str] = Field(default_factory=list)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)
    consolidated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AttributionModelType(StrEnum):
    """Supported deterministic multi-touch attribution models."""

    LINEAR = "linear"
    FIRST_TOUCH = "first_touch"
    LAST_TOUCH = "last_touch"
    TIME_DECAY = "time_decay"
    POSITION_BASED = "position_based"


class Touchpoint(BaseModel):
    """A marketing interaction touchpoint along a conversion journey."""

    channel: str
    campaign_id: str | None = None
    creative_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cost: float = 0.0
    interaction_type: str = "click"


class ConversionPath(BaseModel):
    """A customer conversion path consisting of sequential touchpoints."""

    conversion_id: str
    tenant_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revenue: float = 0.0
    touchpoints: list[Touchpoint] = Field(default_factory=list)


class AttributionWeight(BaseModel):
    """Attributed contribution metrics for a channel, campaign, or creative."""

    channel: str
    campaign_id: str | None = None
    creative_id: str | None = None
    weight: float = 0.0
    attributed_revenue: float = 0.0
    attributed_conversions: float = 0.0


class CreativeDecayMetric(BaseModel):
    """Exponential decay, fatigue status, and lifecycle action recommendation for a creative."""

    creative_id: str
    channel: str
    days_active: float = 0.0
    decay_multiplier: float = 1.0
    fatigue_detected: bool = False
    recommended_action: str = "scale_spend"
    projected_roas: float = 0.0


class RoasMetric(BaseModel):
    """Calculated ROAS for a channel or campaign with denominator safety."""

    channel: str
    campaign_id: str | None = None
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    status: str = "valid"  # "valid", "zero_spend_with_revenue", "zero_spend_zero_revenue"


class DataQualityIndicator(BaseModel):
    """Indicators evaluating telemetry completeness, coverage, and sufficiency."""

    total_events: int = 0
    conversion_count: int = 0
    total_spend: float = 0.0
    total_revenue: float = 0.0
    attribution_coverage: float = 1.0
    missing_spend_count: int = 0
    is_sufficient: bool = True
    warnings: list[str] = Field(default_factory=list)


class AttributionDeliverable(BaseModel):
    """Consolidated deliverable produced by W_LEARN + S_ATTR for T31."""

    deliverable_id: str
    tenant_id: str
    task_id: str
    model_type: AttributionModelType = AttributionModelType.LINEAR
    input_window_start: datetime | None = None
    input_window_end: datetime | None = None
    channel_weights: list[AttributionWeight] = Field(default_factory=list)
    decay_metrics: list[CreativeDecayMetric] = Field(default_factory=list)
    roas_metrics: list[RoasMetric] = Field(default_factory=list)
    data_quality: DataQualityIndicator = Field(default_factory=DataQualityIndicator)
    proposed_learning_deltas: list[str] = Field(default_factory=list)
    confidence: ConfidenceInterval | None = None
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningPromotionProposal(BaseModel):
    """Proposal prepared by W_LEARN to promote a validated learning delta into Institutional Memory."""

    proposal_id: str = Field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:8]}")
    tenant_id: str
    brand_id: str | None = None
    namespace: str = "attribution_heuristics"
    category: str = "attribution"
    statement: str
    justification: str = ""
    source_task_id: str = "task-t31"
    evidence_references: list[str] = Field(default_factory=list)
    method_version: str = "1.0"
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality_metadata: dict[str, Any] = Field(default_factory=dict)
    proposing_agent: str = "W_LEARN"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PromotionResult(BaseModel):
    """Result of IE authorization and governed persistence into Institutional Memory."""

    result_id: str = Field(default_factory=lambda: f"res-{uuid.uuid4().hex[:8]}")
    proposal_id: str
    memory_id: str
    namespace: str
    version: int = 1
    status: str = "promoted"  # "promoted" | "idempotent_noop" | "rejected" | "held"
    provenance_ref: str | None = None
    source_task_id: str = "task-t31"
    cts_state_delta: dict[str, Any] = Field(default_factory=dict)
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str = ""


# ---------------------------------------------------------------------------
# W_DEV Core Contracts (DE-01)
# ---------------------------------------------------------------------------
from app.schemas.development.development_result import (
    DevelopmentEngineIdentity,
    DevelopmentEngineRequest,
    DevelopmentEngineResult,
    DevelopmentEngineStatus,
    DevelopmentTaskGrant,
)

__all__ = [
    "TaskGrant",
    "ContextRequest",
    "ConfidenceInterval",
    "EvidenceEnvelope",
    "DevelopmentDeliverable",
    "CmsSchemaDiff",
    "CodeDiffEntry",
    "UITemplateDefinition",
    "DevelopmentEngineIdentity",
    "DevelopmentEngineStatus",
    "DevelopmentTaskGrant",
    "DevelopmentEngineRequest",
    "DevelopmentEngineResult",
]