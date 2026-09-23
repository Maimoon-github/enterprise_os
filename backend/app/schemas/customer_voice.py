"""Typed Customer Voice schemas, boundaries, and data contracts.

Enforces zero-sandbox W_VOICE coordination, explicit evidence grounding via EvidenceSpan,
methodology-disclosed survey metadata, aspect-level sentiment, descriptive journey
comparisons, and immutable QA assessment contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Re-export legacy customer voice contracts for backwards compatibility
from app.schemas.agent_contracts import (
    AnonymizedSentimentVector,
    CustomerVoiceAnalysisResult,
    CustomerVoiceItem,
    ObjectionProfile,
    SentimentClassification,
)

__all__ = [
    # Legacy compatibility types
    "SentimentClassification",
    "CustomerVoiceItem",
    "AnonymizedSentimentVector",
    "ObjectionProfile",
    "CustomerVoiceAnalysisResult",
    # CV-01 core contracts
    "VoiceWorkflowStage",
    "VOICE_WORKFLOW_SEQUENCE",
    "EvidenceSpan",
    "SurveyMethodology",
    "FeedbackRecord",
    "CustomerVoiceTask",
    "VoiceSpecialistTask",
    "VoiceQAReport",
    "VoiceSpecialistResult",
    "TopicFinding",
    "AspectSentimentFinding",
    "NeedObjectionFinding",
    "JourneyComparison",
    "CustomerVoicePayload",
]


class VoiceWorkflowStage(StrEnum):
    """Fixed Voice specialist workflow stages."""

    DISCOVERY = "VOICE-DISCOVERY"
    THEMES = "VOICE-THEMES"
    SENTIMENT = "VOICE-SENTIMENT"
    NEEDS = "VOICE-NEEDS"
    JOURNEY = "VOICE-JOURNEY"
    QA = "VOICE-QA"
    SYNTHESIS = "W_VOICE"


VOICE_WORKFLOW_SEQUENCE: tuple[
    VoiceWorkflowStage | tuple[VoiceWorkflowStage, ...], ...
] = (
    VoiceWorkflowStage.DISCOVERY,
    (
        VoiceWorkflowStage.THEMES,
        VoiceWorkflowStage.SENTIMENT,
        VoiceWorkflowStage.NEEDS,
    ),
    VoiceWorkflowStage.JOURNEY,
    VoiceWorkflowStage.QA,
    VoiceWorkflowStage.SYNTHESIS,
)


class EvidenceSpan(BaseModel):
    """First-class evidence grounding reference pointing to an exact sanitized record span."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(description="Opaque ID of the referenced sanitized feedback record")
    sanitized_text_hash: str = Field(description="SHA-256 hash of the complete sanitized record text")
    start_offset: int = Field(ge=0, description="Character start offset in sanitized_text")
    end_offset: int = Field(gt=0, description="Character end offset in sanitized_text")
    span_hash: str = Field(description="SHA-256 hash of the exact span text")
    source_ref: str = Field(description="Reference to origin source (e.g. ticket-id, review-id)")
    exact_quote: str | None = Field(default=None, description="Exact span text from sanitized record")


class SurveyMethodology(BaseModel):
    """Survey collection methodology and precision disclosures adhering to AAPOR standards."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    methodology_id: str = Field(description="Unique identifier for this survey methodology")
    population_definition: str | None = Field(default=None, description="Target population definition")
    sampling_method: str | None = Field(
        default=None, description="Sampling approach (probability, non-probability, unknown)"
    )
    sampling_frame: str | None = Field(default=None, description="Sampling frame description")
    collection_mode: str | None = Field(default=None, description="Collection mode (web, phone, in-person)")
    fieldwork_dates: tuple[str, str] | str | None = Field(
        default=None, description="Start and end dates of fieldwork"
    )
    questionnaire_version: str | None = Field(default=None, description="Questionnaire instrument version")
    invited_or_eligible_n: int | None = Field(
        default=None, ge=0, description="Invited or eligible sample size"
    )
    completed_n: int | None = Field(default=None, ge=0, description="Completed interviews/responses count")
    response_rate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="AAPOR response rate proportion"
    )
    response_rate_definition: str | None = Field(
        default=None, description="Specific AAPOR standard formula applied (e.g. RR1, RR3)"
    )
    weighting_method: str | None = Field(default=None, description="Weighting adjustment method applied")
    weight_variables: list[str] = Field(default_factory=list, description="Variables used in weighting")
    design_effect: float | None = Field(default=None, ge=0.0, description="Design effect (DEFF)")
    precision_method: str | None = Field(
        default=None, description="Margin of error or Bayesian credible interval method"
    )
    unknown_reasons: dict[str, str] = Field(
        default_factory=dict, description="Explanations for any unknown/unspecified fields"
    )


class FeedbackRecord(BaseModel):
    """Normalized, sanitized customer feedback record preserving traceability without raw PII."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opaque_record_id: str = Field(description="Pseudonymous or HMAC-based record ID")
    record_hash: str = Field(description="SHA-256 integrity hash of raw/sanitized content")
    source_ref: str = Field(description="Opaque external source reference")
    source_type: str = Field(default="feedback", description="Type of source: review, ticket, survey, etc.")
    channel: str | None = Field(default=None, description="Intake channel (zendesk, amazon, app_store)")
    touchpoint: str | None = Field(default=None, description="Customer journey touchpoint")
    timestamp: str | datetime | None = Field(default=None, description="Timestamp of feedback creation")
    locale: str = Field(default="en", description="Detected or declared locale")
    product_ref: str | None = Field(default=None, description="Referenced product/service ID")
    explicit_segment_refs: list[str] = Field(
        default_factory=list, description="Explicit customer segments from source metadata"
    )
    sanitized_text: str = Field(description="De-identified feedback text")
    redaction_summary: dict[str, int] = Field(
        default_factory=dict, description="Count of redacted entities by PII type"
    )
    injection_flagged: bool = Field(
        default=False, description="True if prompt injection or system instructions were detected"
    )
    dedupe_group: str | None = Field(default=None, description="Cluster ID if item was deduplicated")
    duplicate_members: list[str] = Field(
        default_factory=list, description="Source references or record IDs of duplicate records collapsed into this canonical record"
    )
    survey_methodology_ref: str | None = Field(
        default=None, description="Reference to SurveyMethodology if source is a survey"
    )
    provenance_ref: str | None = Field(default=None, description="W3C PROV lineage reference")



class CustomerVoiceTask(BaseModel):
    """Top-level task contract received and frozen by W_VOICE coordinator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(description="Unique task identifier")
    tenant_id: str = Field(description="Authorized tenant scope")
    brand_id: str | None = Field(default=None, description="Authorized brand scope")
    product_ref: str | None = Field(default=None, description="Target product reference")
    objective: str = Field(description="Customer voice research objective")
    source_refs: list[str] = Field(default_factory=list, description="Approved own-brand source references")
    egress_grant_id: str | None = Field(default=None, description="Attached IE egress grant ID if any")
    workflow_stage: VoiceWorkflowStage = Field(
        default=VoiceWorkflowStage.DISCOVERY, description="Current workflow stage"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Task creation timestamp"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional governance metadata")


class VoiceSpecialistTask(BaseModel):
    """Task delegated by W_VOICE to an individual Voice specialist agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specialist_id: str = Field(description="Target specialist identity (e.g. VOICE-DISCOVERY)")
    parent_task_id: str = Field(description="W_VOICE parent task identifier")
    tenant_id: str = Field(description="Authorized tenant scope")
    stage: VoiceWorkflowStage = Field(description="Workflow stage assigned to specialist")
    immutable_corpus_hash: str | None = Field(
        default=None, description="Integrity hash of the sanitized corpus"
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Specialist task parameters")
    token_budget: int = Field(default=4000, gt=0, description="Token ceiling")
    timeout_seconds: int = Field(default=120, gt=0, description="Execution timeout in seconds")


class VoiceQAReport(BaseModel):
    """Non-mutating evaluative QA report produced by VOICE-QA."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "REVISE", "BLOCK"] = Field(description="Evaluation verdict")
    residual_pii_check: bool = Field(default=True, description="True if no residual PII detected")
    evidence_traceability_check: bool = Field(
        default=True, description="True if all findings resolve to exact evidence spans"
    )
    bias_check: bool = Field(
        default=True, description="True if frequency is not conflated with prevalence"
    )
    contradiction_check: bool = Field(
        default=True, description="True if contradictory feedback is preserved"
    )
    coverage_check: bool = Field(default=True, description="True if required segments/locales covered")
    schema_validity_check: bool = Field(
        default=True, description="True if all outputs adhere to strict schemas"
    )
    candidate_input_hash: str = Field(description="Integrity hash of input before evaluation")
    candidate_output_hash: str = Field(
        description="Integrity hash of output verifying non-mutation (must match input hash)"
    )
    findings: list[str] = Field(default_factory=list, description="QA diagnostic observations")
    block_reasons: list[str] = Field(default_factory=list, description="Reasons for BLOCK or REVISE")
    reidentification_risk: str = Field(
        default="de_identified_residual_risk_retained",
        description="NIST IR 8053 residual re-identification risk statement",
    )


class VoiceSpecialistResult(BaseModel):
    """Execution deliverable produced by a single Voice specialist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specialist_id: str = Field(description="Specialist identity")
    task_id: str = Field(description="Task identifier")
    stage: VoiceWorkflowStage = Field(description="Completed workflow stage")
    success: bool = Field(description="True if specialist execution succeeded")
    input_hash: str = Field(description="Hash of inputs provided to specialist")
    output_hash: str = Field(description="Hash of outputs generated by specialist")
    findings: list[Any] = Field(default_factory=list, description="Extracted findings")
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Grounding evidence spans"
    )
    records: list[FeedbackRecord] = Field(default_factory=list, description="Sanitized FeedbackRecords for discovery stage")
    artifacts: list[str] = Field(default_factory=list, description="Generated artifact references")
    qa_report: VoiceQAReport | None = Field(default=None, description="QA evaluation if applicable")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Execution provenance metadata")
    error: str | None = Field(default=None, description="Error message if execution failed")



class TopicFinding(BaseModel):
    """Clustered theme or topic with diagnostics; observed share is kept distinct from prevalence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topic_id: str = Field(description="Identifier for this topic cluster")
    label: str = Field(description="Descriptive topic label")
    observed_count: int = Field(ge=0, description="Count of items exhibiting this topic")
    observed_share_of_analyzed_corpus: float = Field(
        ge=0.0, le=1.0, description="Observed sample proportion"
    )
    weighted_survey_estimate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Statistically weighted survey estimate if available"
    )
    outlier_or_unassigned_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Proportion of corpus unassigned or deemed outlier"
    )
    cluster_algorithm: str = Field(default="kmeans", description="Clustering algorithm name")
    cluster_version: str = Field(default="1.0", description="Algorithm implementation version")
    cluster_parameters: dict[str, Any] = Field(default_factory=dict, description="Hyperparameters used")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model identifier"
    )
    embedding_model_version: str = Field(default="1.0", description="Embedding model revision")
    cluster_diagnostics: dict[str, Any] = Field(
        default_factory=dict, description="Quality diagnostics (e.g. silhouette_score)"
    )
    representative_evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Exemplar evidence spans grounding this topic"
    )
    trend: Literal["increasing", "decreasing", "stable", "not_assessed"] = Field(
        default="not_assessed",
        description="Temporal trend (requires comparable time windows and change method)",
    )
    inference_scope: Literal["observed_feedback_only", "weighted_survey_sample"] = Field(
        default="observed_feedback_only", description="Statistical boundary of inference"
    )
    population_representativeness: Literal["not_established", "statistically_weighted"] = Field(
        default="not_established", description="Representativeness status"
    )


class AspectSentimentFinding(BaseModel):
    """Aspect-level sentiment scoring with calibration and uncertainty indicators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aspect: str = Field(description="Specific product feature, attribute, or service touchpoint")
    polarity: SentimentClassification | str = Field(
        description="Sentiment polarity classification (POSITIVE, NEGATIVE, NEUTRAL, MIXED)"
    )
    model_score: float = Field(description="Model output score (polarity or sentiment confidence)")
    score_is_calibrated: bool = Field(
        default=False, description="True only if model score is empirically calibrated to a true probability"
    )
    emotion: list[str] = Field(default_factory=list, description="Detected emotions (e.g. frustration, delight)")
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Grounding evidence spans in feedback"
    )
    model_version: str = Field(default="1.0", description="Classifier model version")
    locale: str = Field(default="en", description="Language/locale of analyzed feedback")
    uncertainty_reason: str | None = Field(
        default=None, description="Declared uncertainty reason if score confidence is low"
    )


class NeedObjectionFinding(BaseModel):
    """Customer need, pain point, objection, or desired outcome with customer vocabulary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(description="Unique finding identifier")
    finding_type: Literal["need", "pain_point", "objection", "desired_outcome"] = Field(
        default="objection", description="Classification of the finding"
    )
    theme: str = Field(description="Normalized theme")
    frequency: int = Field(default=1, ge=1, description="Observed occurrence count")
    severity: str = Field(default="low", description="Assessed impact severity (low, medium, high)")
    customer_vocabulary: list[str] = Field(
        default_factory=list, description="Exact phrasing and terms used by customers"
    )
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Grounding evidence spans"
    )
    provenance: dict[str, Any] = Field(default_factory=dict, description="Lineage metadata")


class JourneyComparison(BaseModel):
    """Descriptive channel or touchpoint comparison prohibiting causal inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str = Field(description="Unique comparison identifier")
    channel_or_touchpoint_a: str = Field(description="First channel or touchpoint")
    channel_or_touchpoint_b: str = Field(description="Second channel or touchpoint")
    metric_or_dimension: str = Field(description="Dimension compared (e.g. objection frequency, polarity)")
    comparison_type: Literal["descriptive_comparison"] = Field(
        default="descriptive_comparison",
        description="Must remain descriptive_comparison; causal claims are forbidden",
    )
    comparison_summary: str = Field(
        description="Factual statement of observed difference without causal assertions"
    )
    segment_refs: list[str] = Field(
        default_factory=list, description="Explicit segment metadata referenced"
    )
    time_interval: str | None = Field(default=None, description="Observed time interval")
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Evidence spans supporting the comparison"
    )
    causal_claim_disclaimer: str = Field(
        default="Descriptive comparison only. No causal relationship inferred.",
        description="Mandatory disclaimer preventing causal claims",
    )


class CustomerVoicePayload(BaseModel):
    """Final sanitized Customer Voice deliverable synthesized by W_VOICE."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(description="Governed task ID")
    tenant_id: str = Field(description="Tenant scope")
    product_ref: str | None = Field(default=None, description="Product reference")
    records_analyzed: int = Field(default=0, ge=0, description="Total feedback records analyzed")
    topics: list[TopicFinding] = Field(default_factory=list, description="Discovered topics/themes")
    aspect_sentiment: list[AspectSentimentFinding] = Field(
        default_factory=list, description="Aspect-level sentiment findings"
    )
    needs_and_objections: list[NeedObjectionFinding] = Field(
        default_factory=list, description="Needs, objections, and pain points"
    )
    journey_comparisons: list[JourneyComparison] = Field(
        default_factory=list, description="Descriptive journey comparisons"
    )
    qa_report: VoiceQAReport | None = Field(default=None, description="Independent QA report")
    survey_methodologies: list[SurveyMethodology] = Field(
        default_factory=list, description="Attached survey methodologies if applicable"
    )
    inference_scope: Literal["observed_feedback_only", "weighted_survey_sample"] = Field(
        default="observed_feedback_only", description="Explicit inference boundary"
    )
    population_representativeness: Literal["not_established", "statistically_weighted"] = Field(
        default="not_established", description="Representativeness status"
    )
    reidentification_risk_disclosure: str = Field(
        default="De-identified text carries non-zero residual re-identification risk (NIST IR 8053).",
        description="Required privacy and re-identification disclosure",
    )
    provenance: dict[str, Any] = Field(default_factory=dict, description="W3C PROV lineage audit data")
