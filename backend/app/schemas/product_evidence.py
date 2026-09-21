"""Authoritative Product / Evidence Engine (W_PROD / S_VAL) domain contracts.

Defines machine-validatable schemas for boundary contracts (PE-02),
research protocol, sources, extracted evidence, assessments, formulation bridges,
lab validation, claims, regulatory rules, trace bundles, and review bindings.
Preserves Model-A boundaries, tenant isolation, and strict tamper-evident lineage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==============================================================================
# Enums
# ==============================================================================


class SpecialistRole(str, Enum):
    """The six bounded specialist sub-agents of W_PROD."""

    DISCOVERY = "DISCOVERY"
    PRODUCT_LAB = "PRODUCT_LAB"
    APPRAISAL = "APPRAISAL"
    SAFETY = "SAFETY"
    CLAIMS = "CLAIMS"
    REGULATORY = "REGULATORY"


class SpecialistResultStatus(str, Enum):
    """Execution status of a specialist sub-task."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    NEEDS_CONTEXT = "needs_context"
    NEEDS_CAPABILITY = "needs_capability"
    ESCALATED = "escalated"
    FAILED = "failed"


class EvidenceType(str, Enum):
    """Categorization of evidence documents and sources."""

    PRIMARY_STUDY = "primary_study"
    SYSTEMATIC_REVIEW = "systematic_review"
    LAB_REPORT = "lab_report"
    LEGAL_TEXT = "legal_text"
    OFFICIAL_GUIDANCE = "official_guidance"
    STANDARD = "standard"
    METADATA = "metadata"
    SECONDARY_COMMENTARY = "secondary_commentary"
    OTHER = "other"


class AccessLevel(str, Enum):
    """Actual document access level during evidence acquisition."""

    FULL_TEXT = "full_text"
    ABSTRACT_ONLY = "abstract_only"
    METADATA_ONLY = "metadata_only"
    INDEXED_EXTRACT = "indexed_extract"
    UNAVAILABLE = "unavailable"


class FreshnessStatus(str, Enum):
    """Verification recency and validity status."""

    CURRENT_CHECKED = "current_checked"
    REFRESH_DUE = "refresh_due"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class EvidenceSubject(str, Enum):
    """Subject matter evaluated by the evidence."""

    INGREDIENT = "ingredient"
    FINISHED_PRODUCT = "finished_product"
    ANALOG_PRODUCT = "analog_product"
    OTHER = "other"


class ClaimKind(str, Enum):
    """Distinction between express marketing text and implied customer takeaways."""

    EXPLICIT = "explicit"
    IMPLIED = "implied"


class ClaimStatus(str, Enum):
    """Evidence-backed verification status of a marketing or clinical claim."""

    SUPPORTED_IN_SCOPE = "supported_in_scope"
    QUALIFIED_SUPPORT = "qualified_support"
    INSUFFICIENT = "insufficient"
    CONFLICTED = "conflicted"
    NOT_ASSESSED = "not_assessed"


class RuleForce(str, Enum):
    """Legal or organizational authority of a compliance rule."""

    LAW = "law"
    REGULATION = "regulation"
    GUIDANCE = "guidance"
    STANDARD = "standard"
    ORGANIZATIONAL_POLICY = "organizational_policy"


class RuleStatus(str, Enum):
    """Applicability and currency status of a regulatory requirement."""

    VERIFIED_APPLICABLE = "verified_applicable"
    PENDING = "pending"
    SUPERSEDED = "superseded"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class MappingRelation(str, Enum):
    """Evidence support direction for a claim proposition."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


class EvidenceRelevance(str, Enum):
    """Relevance and bridging applicability of the evidence to the target product."""

    DIRECT = "direct"
    BRIDGE_REQUIRED = "bridge_required"
    INDIRECT = "indirect"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class SafetyStatus(str, Enum):
    """Product safety evaluation status."""

    CONCERN_IDENTIFIED = "concern_identified"
    INSUFFICIENT = "insufficient"
    NO_CONCERN_IDENTIFIED_IN_SCOPE = "no_concern_identified_in_scope"
    NOT_ASSESSED = "not_assessed"


class RuleApplicationResult(str, Enum):
    """Outcome of evaluating a rule against a product or claim."""

    MEETS_CHECKED_REQUIREMENT = "meets_checked_requirement"
    DOES_NOT_MEET_CHECKED_REQUIREMENT = "does_not_meet_checked_requirement"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ReviewStatus(str, Enum):
    """Human-in-the-loop sign-off status for dossiers and claims."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISIONS_REQUESTED = "revisions_requested"


# ==============================================================================
# Base Contract
# ==============================================================================


class ProductEvidenceBaseModel(BaseModel):
    """Base schema enforcing strict unknown-field rejection and canonical hashing."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON bytes for tamper-evident hashing."""
        dumped = self.model_dump(mode="json")
        return json.dumps(dumped, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_hash(self) -> str:
        """Compute SHA-256 tamper-evident digest."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


# ==============================================================================
# Boundary Contracts (Task 4)
# ==============================================================================


class ProductEvidenceTask(ProductEvidenceBaseModel):
    """Task definition dispatched from Intelligence Engine to W_PROD."""

    schema_version: Literal["1.0"] = "1.0"
    task_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    parent_grant_ref: str = Field(min_length=1, max_length=200)
    parent_grant_hash: str = Field(min_length=1, max_length=128)
    context_version: str = Field(min_length=1, max_length=50)
    context_hash: str = Field(min_length=1, max_length=128)
    product_version: str = Field(min_length=1, max_length=100)
    category_hypothesis: str = Field(default="cosmetics", max_length=200)
    jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    assessment_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    intended_use_or_populations: list[str] = Field(default_factory=list, max_length=100)
    claim_asset_refs: list[str] = Field(default_factory=list, max_length=200)
    objectives: list[str] = Field(default_factory=list, max_length=50)
    protocol_scope: dict[str, Any] = Field(default_factory=dict)
    allowed_s_val_operations: list[str] = Field(default_factory=list, max_length=50)
    source_or_egress_policy_refs: list[str] = Field(default_factory=list, max_length=50)
    profile_refs: dict[str, str] = Field(default_factory=dict)
    budget_limit_tokens: int = Field(default=10000, ge=1)
    deadline_utc: datetime | None = None
    stop_or_review_rules: list[str] = Field(default_factory=list, max_length=50)


class SpecialistTask(ProductEvidenceBaseModel):
    """Sub-task dispatched from W_PROD to an isolated S_VAL specialist."""

    schema_version: Literal["1.0"] = "1.0"
    task_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=200)
    parent_task_id: str = Field(min_length=1, max_length=200)
    specialist_role: SpecialistRole
    operation: str = Field(min_length=1, max_length=100)
    input_manifest: list[str] = Field(default_factory=list, max_length=500)
    context_slice: dict[str, Any] = Field(default_factory=dict)
    profile_ref: str = Field(min_length=1, max_length=200)
    profile_version: str = "1.0"
    profile_digest: str = Field(default="", max_length=128)
    schema_ids: list[str] = Field(default_factory=list, max_length=50)
    delegated_token_limit: int = Field(default=5000, ge=1)
    policy_refs: list[str] = Field(default_factory=list, max_length=50)
    deadline_utc: datetime | None = None
    output_limits: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(default="", max_length=200)
    attempt_id: str = Field(default="1", max_length=50)


class SpecialistResult(ProductEvidenceBaseModel):
    """Structured result returned by an isolated S_VAL specialist."""

    schema_version: Literal["1.0"] = "1.0"
    task_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=50)
    tenant_id: str = Field(min_length=1, max_length=200)
    specialist_role: SpecialistRole
    operation: str = Field(min_length=1, max_length=100)
    status: SpecialistResultStatus
    typed_findings: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list, max_length=1000)
    extracted_evidence_refs: list[str] = Field(default_factory=list, max_length=1000)
    assessment_refs: list[str] = Field(default_factory=list, max_length=1000)
    identified_gaps: list[str] = Field(default_factory=list, max_length=500)
    identified_conflicts: list[str] = Field(default_factory=list, max_length=500)
    sanitized_artifacts: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    provenance_fragments: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_outcomes: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    error_or_review_reasons: list[str] = Field(default_factory=list, max_length=100)


class ProductContextRequest(ProductEvidenceBaseModel):
    """Formal request for additional read-only context routed through IE."""

    request_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=200)
    specialist_role: SpecialistRole
    missing_field_or_source: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1000)
    affected_claim_or_question: str = Field(min_length=1, max_length=1000)
    minimum_scope_needed: str = Field(min_length=1, max_length=500)
    is_blocking: bool = True
    reason: str = Field(min_length=1, max_length=1000)


class ProductReviewBinding(ProductEvidenceBaseModel):
    """HITL review requirement and binding for a verified dossier."""

    dossier_hash: str = Field(min_length=1, max_length=128)
    product_version: str = Field(min_length=1, max_length=100)
    formula_version: str = Field(min_length=1, max_length=100)
    claim_versions: list[str] = Field(default_factory=list, max_length=100)
    asset_versions: list[str] = Field(default_factory=list, max_length=100)
    target_territory: str = Field(min_length=1, max_length=50)
    locale: str = Field(default="en_US", max_length=20)
    effective_date: str = Field(min_length=1, max_length=50)
    required_reviewer_role: str = Field(min_length=1, max_length=100)
    qualification_requirements: list[str] = Field(default_factory=list, max_length=50)
    review_reasons: list[str] = Field(default_factory=list, max_length=100)
    approval_status: ReviewStatus = ReviewStatus.PENDING
    approval_ref: str | None = None


# ==============================================================================
# Domain Records (Task 5)
# ==============================================================================


class ResearchProtocol(ProductEvidenceBaseModel):
    """Systematic research or evidence assessment protocol."""

    protocol_id: str = Field(min_length=1, max_length=200)
    question_framing: str = Field(min_length=1, max_length=4000)
    assessment_type: Literal["rapid", "systematic", "targeted", "update"] = "targeted"
    product_scope: str = Field(default="", max_length=500)
    populations: list[str] = Field(default_factory=list, max_length=50)
    outcomes: list[str] = Field(default_factory=list, max_length=50)
    exposure: str = Field(default="", max_length=500)
    comparator: str = Field(default="", max_length=500)
    inclusion_criteria: list[str] = Field(default_factory=list, max_length=100)
    exclusion_criteria: list[str] = Field(default_factory=list, max_length=100)
    target_sources: list[str] = Field(default_factory=list, max_length=50)
    source_classes: list[str] = Field(default_factory=list, max_length=50)
    jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    language_and_date_limits: dict[str, Any] = Field(default_factory=dict)
    search_syntax: str = Field(default="", max_length=4000)
    planned_methods: list[str] = Field(default_factory=list, max_length=50)
    stopping_rules: list[str] = Field(default_factory=list, max_length=50)
    budgets: dict[str, Any] = Field(default_factory=dict)
    protocol_version: str = "1.0"
    amendments: list[str] = Field(default_factory=list, max_length=50)


class SearchRun(ProductEvidenceBaseModel):
    """Auditable evidence discovery search execution."""

    run_id: str = Field(min_length=1, max_length=200)
    protocol_id: str = Field(min_length=1, max_length=200)
    source_system_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=4000)
    interface_version: str = Field(default="", max_length=100)
    started_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at_utc: datetime | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    pagination_cursor: str | None = Field(default=None, max_length=500)
    results_count: int = Field(default=0, ge=0)
    screened_count: int = Field(default=0, ge=0)
    screening_outcomes: dict[str, int] = Field(default_factory=dict)
    inaccessible_or_truncated_results: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    stopping_reason: str = Field(default="", max_length=500)


class SourceRecord(ProductEvidenceBaseModel):
    """External scientific, regulatory, or laboratory reference source."""

    id: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=4096)
    identifier: str | None = Field(default=None, max_length=300)
    issuer_or_authors: list[str] = Field(default_factory=list, max_length=100)
    title: str = Field(default="", max_length=2000)
    jurisdiction: str = Field(default="not_applicable", max_length=200)
    evidence_type: EvidenceType
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    access: AccessLevel
    language: str = Field(default="en", max_length=20)
    authenticity_status: Literal["verified", "partial", "unresolved", "compromised"] = "verified"
    freshness: FreshnessStatus = FreshnessStatus.CURRENT_CHECKED
    freshness_checked_at: datetime | None = None
    snapshot_ref: str | None = Field(default=None, max_length=200)
    provenance_ref: str = Field(min_length=1, max_length=200)
    rights_or_limitations: list[str] = Field(default_factory=list, max_length=50)
    correction_or_retraction_status: Literal["none", "corrected", "expression_of_concern", "retracted"] = "none"
    source_location: str = Field(default="", max_length=1000)
    study_family_id: str = Field(default="", max_length=200)
    is_secondary_lead: bool = False

    @model_validator(mode="after")
    def check_url_or_identifier(self) -> SourceRecord:
        if not self.url and not self.identifier:
            raise ValueError("SourceRecord requires at least one of 'url' or 'identifier'.")
        return self


class SourceSnapshot(ProductEvidenceBaseModel):
    """Immutable captured representation of a retrieved document."""

    snapshot_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(min_length=1, max_length=128)
    media_type: str = Field(default="text/html", max_length=100)
    byte_length: int = Field(default=0, ge=0)
    retrieval_activity_id: str = Field(min_length=1, max_length=200)
    requested_url: str = Field(default="", max_length=4096)
    final_url: str = Field(default="", max_length=4096)
    redirect_trace: list[str] = Field(default_factory=list, max_length=20)
    response_status: int = Field(default=200, ge=100, le=599)
    capture_tool_version: str = Field(default="1.0", max_length=50)
    captured_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExtractedEvidence(ProductEvidenceBaseModel):
    """Atomized, referenced finding extracted from a source snapshot."""

    id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    snapshot_ref: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=12000)
    subject: EvidenceSubject
    outcome: str = Field(min_length=1, max_length=12000)
    assessment_ref: str = Field(min_length=1, max_length=200)
    activity_ref: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(default="", max_length=12000)
    extract_hash: str = Field(default="", max_length=128)
    original_value: str = Field(default="", max_length=1000)
    normalized_value: str = Field(default="", max_length=1000)
    study_family_id: str = Field(default="", max_length=200)
    study_design: str = Field(default="", max_length=200)
    material_or_batch: str = Field(default="", max_length=500)
    population_or_subject_type: str = Field(default="", max_length=500)
    comparator: str = Field(default="", max_length=500)
    adverse_events: list[str] = Field(default_factory=list, max_length=50)
    extraction_method: str = Field(default="automated_validation", max_length=200)


class EvidenceAssessment(ProductEvidenceBaseModel):
    """Scientific quality, certainty, and relevance appraisal for evidence items."""

    id: str = Field(min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    assessor_activity_id: str = Field(min_length=1, max_length=200)
    method_version: str = Field(default="GRADE_v1", max_length=100)
    source_integrity: Literal["verified", "partial", "unresolved", "compromised"] = "verified"
    risk_of_bias: Literal["low", "some_concerns", "high", "not_assessed"] = "low"
    relevance: EvidenceRelevance = EvidenceRelevance.DIRECT
    precision: Literal["precise", "serious_imprecision", "very_serious_imprecision", "not_assessed"] = "precise"
    consistency: Literal["consistent", "explainable_difference", "unresolved_conflict", "too_sparse", "not_assessed"] = "consistent"
    certainty: Literal["high", "moderate", "low", "very_low", "not_assessed"] = "high"
    justification: str = Field(default="", max_length=4000)
    supporting_source_locations: list[str] = Field(default_factory=list, max_length=50)


class FormulationEvidenceBridge(ProductEvidenceBaseModel):
    """Scientific comparability assessment between studied ingredient/analog and finished product."""

    bridge_id: str = Field(min_length=1, max_length=200)
    studied_material: str = Field(min_length=1, max_length=500)
    proposed_product: str = Field(min_length=1, max_length=500)
    identity_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    concentration_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    vehicle_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    route_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    exposure_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    population_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    duration_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    endpoint_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    manufacturing_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    packaging_comparability: Literal["match", "mismatch", "unknown", "not_applicable"] = "match"
    overall_relevance: EvidenceRelevance = EvidenceRelevance.DIRECT
    scientific_rationale: str = Field(min_length=1, max_length=4000)
    limits_and_conditions: list[str] = Field(default_factory=list, max_length=50)
    requires_expert_review: bool = False


class NormalizedMeasurement(ProductEvidenceBaseModel):
    """Deterministic normalized analytical measurement record."""

    original_value: Any
    original_unit: str = Field(min_length=1, max_length=50)
    normalized_value: Any
    normalized_unit: str = Field(min_length=1, max_length=50)
    conversion_formula: str = Field(default="", max_length=500)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    precision: int | None = None
    uncertainty: float | None = None
    lod: float | None = None
    loq: float | None = None
    is_nondetect: bool = False


class LabValidation(ProductEvidenceBaseModel):
    """Laboratory test result verification and certificate audit record."""

    report_id: str = Field(min_length=1, max_length=200)
    report_version: str = "1.0"
    report_hash: str = Field(default="", max_length=128)
    issuer_lab_name: str = Field(min_length=1, max_length=500)
    lab_accreditation: str = Field(default="", max_length=500)
    accreditation_verified: bool = False
    accreditation_scope_covers_test: bool = False
    accreditation_expiry_date: str | None = Field(default=None, max_length=50)
    test_method: str = Field(min_length=1, max_length=500)
    method_version: str = Field(default="1.0", max_length=50)
    sample_or_batch_id: str = Field(min_length=1, max_length=200)
    product_linkage_verified: bool = False
    sampling_date: str | None = Field(default=None, max_length=50)
    receipt_date: str | None = Field(default=None, max_length=50)
    test_date: str | None = Field(default=None, max_length=50)
    chain_of_custody_verified: bool = False
    analyte_or_endpoints: list[str] = Field(default_factory=list, max_length=100)
    raw_results: dict[str, Any] = Field(default_factory=dict)
    normalized_results: dict[str, Any] = Field(default_factory=dict)
    units: str = Field(default="", max_length=50)
    lod_loq: dict[str, Any] = Field(default_factory=dict)
    measurement_uncertainty: dict[str, Any] = Field(default_factory=dict)
    specification_limit_source: str = Field(default="", max_length=1000)
    decision_rule: str = Field(default="", max_length=1000)
    deviations: list[str] = Field(default_factory=list, max_length=50)
    reviewer_requirements: list[str] = Field(default_factory=list, max_length=50)
    validation_outcome: Literal["VALIDATED", "DEVIATIONS_NOTED", "REJECTED"] = "VALIDATED"
    conformity_assessment: Literal["PASS", "FAIL", "UNKNOWN", "REVIEW_REQUIRED"] = "UNKNOWN"


class ClaimRecord(ProductEvidenceBaseModel):
    """Atomic marketing or product claim interpretation."""

    id: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0", min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=12000)
    kind: ClaimKind = ClaimKind.EXPLICIT
    asset_ref: str = Field(min_length=1, max_length=200)
    asset_location: str = Field(min_length=1, max_length=12000)
    jurisdiction: str = Field(default="US", min_length=1, max_length=200)
    locale: str = Field(default="en_US", min_length=1, max_length=200)
    interpretation_reason: str = Field(min_length=1, max_length=12000)
    status: ClaimStatus = ClaimStatus.NOT_ASSESSED
    activity_ref: str = Field(min_length=1, max_length=200)
    propositions: list[str] = Field(default_factory=list, max_length=50)
    qualifiers: list[str] = Field(default_factory=list, max_length=50)
    channel: str = Field(default="packaging", max_length=200)
    audience: str = Field(default="general_consumer", max_length=200)
    product_version: str = Field(default="1.0", max_length=100)
    asset_hash: str = Field(default="", max_length=128)
    proposed_narrower_wording: str = Field(default="", max_length=4000)
    scope_limitations: list[str] = Field(default_factory=list, max_length=50)
    human_review_required: bool = False


class ClaimEvidenceEdge(ProductEvidenceBaseModel):
    """Claim-to-evidence and claim-to-rule linkage."""

    id: str = Field(min_length=1, max_length=200)
    claim_id: str = Field(min_length=1, max_length=200)
    evidence_id: str = Field(min_length=1, max_length=200)
    rule_ids: list[str] = Field(default_factory=list, max_length=100)
    relation: MappingRelation
    relevance: EvidenceRelevance
    bridge_ref: str | None = Field(default=None, max_length=200)
    assessment_ref: str | None = Field(default=None, max_length=200)
    scope_dimensions: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list, max_length=100)
    activity_ref: str = Field(min_length=1, max_length=200)


class SafetyAssessment(ProductEvidenceBaseModel):
    """Toxicological and cosmetic safety evaluation."""

    assessment_id: str = Field(min_length=1, max_length=200)
    product_version: str = Field(min_length=1, max_length=100)
    hazards_evaluated: list[str] = Field(default_factory=list, max_length=100)
    exposure_scenario: str = Field(min_length=1, max_length=2000)
    vulnerable_populations_considered: list[str] = Field(default_factory=list, max_length=50)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    adverse_signals: list[str] = Field(default_factory=list, max_length=50)
    status: SafetyStatus = SafetyStatus.NOT_ASSESSED
    relevant_endpoints: list[str] = Field(default_factory=list, max_length=50)
    exposure_assumptions: dict[str, Any] = Field(default_factory=dict)
    scoped_conditions: dict[str, Any] = Field(default_factory=dict)
    limitations_or_uncertainties: list[str] = Field(default_factory=list, max_length=100)
    risk_characterization_limitations: list[str] = Field(default_factory=list, max_length=100)
    qualified_reviewer_required: bool = True


class RegulatoryRule(ProductEvidenceBaseModel):
    """Applicable statutory or administrative compliance requirement."""

    id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=12000)
    jurisdiction: str = Field(min_length=1, max_length=200)
    product_class: str = Field(default="cosmetics", min_length=1, max_length=200)
    force: RuleForce
    authority: str = Field(default="", max_length=200)
    instrument: str = Field(default="", max_length=500)
    section_or_annex: str = Field(default="", max_length=500)
    effective_from: str | None = Field(default=None, max_length=50)
    effective_to: str | None = Field(default=None, max_length=50)
    transition_period_end: str | None = Field(default=None, max_length=50)
    repeal_date: str | None = Field(default=None, max_length=50)
    superseded_by: str | None = Field(default=None, max_length=200)
    status: RuleStatus = RuleStatus.VERIFIED_APPLICABLE
    activity_ref: str = Field(min_length=1, max_length=200)
    rule_summary: str = Field(default="", max_length=4000)


class RuleApplication(ProductEvidenceBaseModel):
    """Outcome of applying a regulatory rule to a specific claim or product."""

    application_id: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    rule_id: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(min_length=1, max_length=200)
    product_class: str = Field(min_length=1, max_length=200)
    outcome: RuleApplicationResult
    assessment_date: str = Field(default="", max_length=50)
    intended_use: str = Field(default="", max_length=500)
    escalation_required: bool = False
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)
    severity_if_breached: Literal["low", "medium", "high", "critical"] = "medium"


class ConflictRecord(ProductEvidenceBaseModel):
    """Record of contradictory findings across evaluated evidence."""

    conflict_id: str = Field(min_length=1, max_length=200)
    affected_proposition_or_claim: str = Field(min_length=1, max_length=2000)
    conflicting_evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    incompatibility_type: str = Field(min_length=1, max_length=500)
    comparable_dimensions: list[str] = Field(default_factory=list, max_length=50)
    noncomparable_dimensions: list[str] = Field(default_factory=list, max_length=50)
    reconciliation_attempt: str = Field(default="", max_length=2000)
    reconciliation_or_sensitivity_method: str = Field(default="", max_length=1000)
    unresolved_impact: str = Field(min_length=1, max_length=2000)
    next_action_proposal: str = Field(min_length=1, max_length=2000)


class EvidenceGap(ProductEvidenceBaseModel):
    """Missing substantiation, inaccessible source, or research gap."""

    id: str = Field(min_length=1, max_length=200)
    affected_ids: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=12000)
    blocking: bool = True
    activity_ref: str = Field(min_length=1, max_length=200)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    proposed_remediation: str = Field(default="", max_length=2000)
    gap_kind: Literal[
        "no_study_found",
        "no_suitable_study_found",
        "inaccessible_evidence",
        "missing_endpoint_coverage",
        "missing_exposure_coverage",
        "missing_population_coverage",
        "insufficient_precision",
        "supports_absence_of_effect",
        "other",
    ] = "other"


class DossierValidation(ProductEvidenceBaseModel):
    """Structural and semantic verification report for an assembled dossier."""

    schema_version: Literal["1.0"] = "1.0"
    validator_version: str = "1.0"
    dossier_digest: str = Field(default="", max_length=128)
    reference_integrity_pass: bool = True
    evidence_completeness: float = Field(default=1.0, ge=0.0, le=1.0)
    rule_freshness_pass: bool = True
    contradictions_detected: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=200)
    blocking_errors: list[str] = Field(default_factory=list, max_length=100)
    structural_status: Literal["VALID", "FLAGGED", "INVALID"] = "VALID"


# ==============================================================================
# Trace Bundle and Full Payload (Tasks 4, 5, 8, 9)
# ==============================================================================

PROHIBITED_CLAIM_PATTERNS = [
    re.compile(r"\bcures?\b", re.IGNORECASE),
    re.compile(r"\b100% guaranteed\b", re.IGNORECASE),
    re.compile(r"\bprevents? all\b", re.IGNORECASE),
    re.compile(r"\bpermanent elimination\b", re.IGNORECASE),
]


class TraceBundle(ProductEvidenceBaseModel):
    """Normative traceability bundle matching Section 9.4 Draft 2020-12 specification."""

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    product_version: str = Field(min_length=1, max_length=200)
    claims: list[ClaimRecord] = Field(default_factory=list, max_length=1000)
    evidence: list[ExtractedEvidence] = Field(default_factory=list, max_length=10000)
    sources: list[SourceRecord] = Field(default_factory=list, max_length=10000)
    rules: list[RegulatoryRule] = Field(default_factory=list, max_length=10000)
    mappings: list[ClaimEvidenceEdge] = Field(default_factory=list, max_length=20000)
    gaps: list[EvidenceGap] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def validate_semantic_invariants(self) -> TraceBundle:
        """Enforce semantic invariants across claim-evidence-rule linkages."""
        source_ids = {s.id for s in self.sources}
        evidence_ids = {e.id: e for e in self.evidence}
        rule_ids = {r.id: r for r in self.rules}
        claim_ids = {c.id: c for c in self.claims}

        # Invariant 1: Source references must resolve
        for ev in self.evidence:
            if ev.source_id not in source_ids:
                raise ValueError(
                    f"Referential integrity failure: ExtractedEvidence '{ev.id}' references "
                    f"unknown source '{ev.source_id}'."
                )

        for r in self.rules:
            if r.source_id not in source_ids:
                raise ValueError(
                    f"Referential integrity failure: RegulatoryRule '{r.id}' references "
                    f"unknown source '{r.source_id}'."
                )

        # Invariant 4: Mappings must resolve claim, evidence, and rule IDs
        for m in self.mappings:
            if m.claim_id not in claim_ids:
                raise ValueError(
                    f"Referential integrity failure: Mapping '{m.id}' references unknown claim '{m.claim_id}'."
                )
            if m.evidence_id not in evidence_ids:
                raise ValueError(
                    f"Referential integrity failure: Mapping '{m.id}' references unknown evidence '{m.evidence_id}'."
                )
            for rid in m.rule_ids:
                if rid not in rule_ids:
                    raise ValueError(
                        f"Referential integrity failure: Mapping '{m.id}' references unknown rule '{rid}'."
                    )

            # Invariant 6: Ingredient evidence supporting a finished-product claim requires a bridge
            linked_ev = evidence_ids[m.evidence_id]
            if (
                linked_ev.subject == EvidenceSubject.INGREDIENT
                and m.relation == MappingRelation.SUPPORTS
                and not m.bridge_ref
            ):
                raise ValueError(
                    f"Invariant violation in mapping '{m.id}': Ingredient-level evidence '{m.evidence_id}' "
                    f"supporting claim '{m.claim_id}' requires a valid 'bridge_ref'."
                )

        # Invariant: Prohibited absolute claims cannot be marked supported
        for c in self.claims:
            for pattern in PROHIBITED_CLAIM_PATTERNS:
                if pattern.search(c.text) and c.status == ClaimStatus.SUPPORTED_IN_SCOPE:
                    raise ValueError(
                        f"Invariant violation: Claim '{c.id}' contains prohibited pattern '{pattern.pattern}' "
                        f"and cannot be marked '{ClaimStatus.SUPPORTED_IN_SCOPE.value}'."
                    )

        # Invariant 2: Gaps must cite known objects
        known_all_ids = set(claim_ids) | set(evidence_ids) | set(source_ids) | set(rule_ids)
        for g in self.gaps:
            for aff_id in g.affected_ids:
                if aff_id not in known_all_ids and not aff_id.startswith("unsearched:"):
                    raise ValueError(
                        f"Gap '{g.id}' references unknown affected ID '{aff_id}'."
                    )

        return self


class ProductEvidencePayload(ProductEvidenceBaseModel):
    """Complete, typed dossier payload returned through the EvidenceEnvelope."""

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: str = Field(min_length=1, max_length=200)
    product_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(min_length=1, max_length=500)
    product_version: str = Field(min_length=1, max_length=100)
    trace_bundle: TraceBundle
    protocols: list[ResearchProtocol] = Field(default_factory=list, max_length=100)
    search_runs: list[SearchRun] = Field(default_factory=list, max_length=500)
    snapshots: list[SourceSnapshot] = Field(default_factory=list, max_length=1000)
    assessments: list[EvidenceAssessment] = Field(default_factory=list, max_length=1000)
    formulation_bridges: list[FormulationEvidenceBridge] = Field(default_factory=list, max_length=100)
    lab_validations: list[LabValidation] = Field(default_factory=list, max_length=100)
    safety_assessments: list[SafetyAssessment] = Field(default_factory=list, max_length=100)
    rule_applications: list[RuleApplication] = Field(default_factory=list, max_length=1000)
    conflicts: list[ConflictRecord] = Field(default_factory=list, max_length=500)
    dossier_validation: DossierValidation | None = None
    review_binding: ProductReviewBinding | None = None


def export_trace_bundle_json_schema() -> dict[str, Any]:
    """Generate Draft 2020-12 compatible JSON Schema from authoritative TraceBundle model."""
    schema = TraceBundle.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:enterprise-os:w-prod:trace-bundle:1.0"
    return schema
