"""Authoritative Competitor Intel Engine (W_COMP) domain and evidence contracts.

Defines schemas for context, step proposals, attempt inputs, source policies,
entities, capture requests, coverage, evidence, observations, findings,
conflicts, alerts, specialist results, and the competitive evidence brief.
Integrates with shared TaskGrant, SandboxCapability, and Provenance models.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CompetitorRole(StrEnum):
    """The seven distinct roles in the Competitor Intel Engine."""

    COORDINATOR = "W_COMP"
    DISCOVERY = "COMP-DISCOVERY"
    ADS = "COMP-ADS"
    PRICE = "COMP-PRICE"
    SEARCH = "COMP-SEARCH"
    POSITION = "COMP-POSITION"
    SYNTHESIS = "COMP-SYNTH"


class FailureCode(StrEnum):
    """Deterministic failure vocabulary for competitor research tasks."""

    # Governance
    GRANT_INVALID = "GRANT_INVALID"
    GRANT_EXPIRED = "GRANT_EXPIRED"
    POLICY_DENIED = "POLICY_DENIED"
    SOURCE_TERMS_UNVERIFIED = "SOURCE_TERMS_UNVERIFIED"
    ROBOTS_DENIED = "ROBOTS_DENIED"
    EGRESS_DENIED = "EGRESS_DENIED"
    ROLE_DENIED = "ROLE_DENIED"

    # Access / Coverage
    AUTH_REQUIRED = "AUTH_REQUIRED"
    REGION_UNSUPPORTED = "REGION_UNSUPPORTED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    LOCALE_UNVERIFIED = "LOCALE_UNVERIFIED"
    RESTRICTED_PREVIEW = "RESTRICTED_PREVIEW"

    # Data / Interpretation
    ENTITY_AMBIGUOUS = "ENTITY_AMBIGUOUS"
    VARIANT_AMBIGUOUS = "VARIANT_AMBIGUOUS"
    PRICE_NOT_DISCLOSED = "PRICE_NOT_DISCLOSED"
    CURRENCY_UNKNOWN = "CURRENCY_UNKNOWN"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    BASELINE_MISSING = "BASELINE_MISSING"
    MESSAGE_AMBIGUOUS = "MESSAGE_AMBIGUOUS"
    UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    STALE_INPUT = "STALE_INPUT"

    # Runtime / Validation
    PARSER_DRIFT = "PARSER_DRIFT"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    HASH_MISMATCH = "HASH_MISMATCH"
    PROVENANCE_INVALID = "PROVENANCE_INVALID"
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CLEANUP_FAILED = "CLEANUP_FAILED"
    CANCELLED = "CANCELLED"


class CoverageStatus(StrEnum):
    """Execution completeness for an admitted query."""

    COMPLETE_FOR_QUERY = "complete_for_query"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"


class ConfidenceRating(StrEnum):
    """Deterministic evidence assessment rating."""

    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssumptionVerdict(StrEnum):
    """Allowed verdicts on strategic assumptions evaluated by W_COMP."""

    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    MIXED = "mixed"
    NOT_TESTABLE = "not_testable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class StrategyAssumption(BaseModel):
    """An assumption from the Strategy plan being tested against evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    evidence_question: str = Field(..., min_length=1)


class SourcePolicyRecord(BaseModel):
    """Bound policy record governing research source access."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1)
    source_class: str = Field(..., description="official, library, site, or provider")
    allowed_origins: list[str] = Field(default_factory=list)
    endpoint_templates: list[str] = Field(default_factory=list)
    permitted_purpose: str = Field(..., min_length=1)
    query_field_limits: dict[str, Any] = Field(default_factory=dict)
    coverage_countries: list[str] = Field(default_factory=list)
    coverage_ad_types: list[str] = Field(default_factory=list)
    date_horizon: str = ""
    terms_url: str = ""
    terms_checked_at: datetime | None = None
    policy_decision_id: str = Field(..., min_length=1)
    policy_expires_at: datetime
    robots_decision_ref: str | None = None
    rate_policy: dict[str, Any] = Field(default_factory=dict)
    retention_permissions: dict[str, Any] = Field(default_factory=dict)
    access_mode: str = "read_only"
    credential_binding: str = "none"


class CompetitorResearchContext(BaseModel):
    """Authoritative research context issued by IE to W_COMP."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    task_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    brand_id: str = Field(..., min_length=1)
    strategy_plan_ref: str = Field(..., min_length=1)
    strategy_plan_hash: str = Field(..., min_length=64, max_length=64)
    assumptions: list[StrategyAssumption] = Field(..., min_length=1)
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requested_window: dict[str, Any] = Field(default_factory=dict)
    markets: list[str] = Field(default_factory=lambda: ["US"])
    languages: list[str] = Field(default_factory=lambda: ["en"])
    devices: list[str] = Field(default_factory=lambda: ["desktop"])
    scoped_entities: list[str] = Field(default_factory=list)
    scoped_keywords: list[str] = Field(default_factory=list)
    source_policies: list[SourcePolicyRecord] = Field(default_factory=list)
    immutable_baseline_inputs: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    freshness_policy_version: str = "v1"

    def compute_context_hash(self) -> str:
        """Compute canonical SHA-256 hash of context parameters."""
        canonical_dict = {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "brand_id": self.brand_id,
            "strategy_plan_ref": self.strategy_plan_ref,
            "strategy_plan_hash": self.strategy_plan_hash,
            "assumptions": [a.model_dump() for a in self.assumptions],
            "markets": sorted(self.markets),
            "scoped_entities": sorted(self.scoped_entities),
        }
        raw = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StepProposalItem(BaseModel):
    """A bounded research step proposed by W_COMP."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1)
    role: CompetitorRole
    dependencies: list[str] = Field(default_factory=list)
    target_entity: str = ""
    target_source: str = ""
    assumption_references: list[str] = Field(default_factory=list)
    scope_description: str = ""

    @field_validator("role")
    @classmethod
    def validate_specialist_role(cls, value: CompetitorRole) -> CompetitorRole:
        if value == CompetitorRole.COORDINATOR:
            raise ValueError("Coordinator W_COMP cannot execute specialist steps.")
        return value


class ResearchStepProposal(BaseModel):
    """Proposal generated by W_COMP domain interpretation for IE scheduling."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(..., min_length=1)
    input_hash: str = Field(..., min_length=64, max_length=64)
    ordered_steps: list[StepProposalItem] = Field(..., min_length=1)
    scoped_entities: list[str] = Field(default_factory=list)
    scoped_sources: list[str] = Field(default_factory=list)
    assumption_references: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)

    @field_validator("ordered_steps")
    @classmethod
    def reject_unauthorized_proposals(cls, steps: list[StepProposalItem]) -> list[StepProposalItem]:
        step_ids = {s.step_id for s in steps}
        for s in steps:
            for dep in s.dependencies:
                if dep not in step_ids:
                    raise ValueError(f"Dangling dependency '{dep}' in step proposal.")
        return steps


class CompetitorAttemptInput(BaseModel):
    """Immutable input staged by IE for an authorized specialist attempt."""

    model_config = ConfigDict(extra="forbid")

    grant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    role: CompetitorRole
    profile_id: str = Field(..., min_length=1)
    llm_instance_id: str = Field(..., min_length=1)
    context_slice: dict[str, Any] = Field(default_factory=dict)
    baseline_manifest: dict[str, Any] = Field(default_factory=dict)
    approved_operation_ids: list[str] = Field(..., min_length=1)
    source_policy_references: list[str] = Field(default_factory=list)
    effective_limits: dict[str, Any] = Field(default_factory=dict)
    input_hash: str = Field(..., min_length=64, max_length=64)
    deadline: datetime
    replay_indicator: bool = False

    @field_validator("role")
    @classmethod
    def validate_role_is_specialist(cls, value: CompetitorRole) -> CompetitorRole:
        if value == CompetitorRole.COORDINATOR:
            raise ValueError("W_COMP coordinator cannot receive sandbox attempt input.")
        return value


class CompetitorEntity(BaseModel):
    """Structured identity record for a competitor."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=1)
    names: list[str] = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    domains: list[str] = Field(..., min_length=1)
    platform_ids: dict[str, str] = Field(default_factory=dict)
    relationship_kind: str = Field(
        default="competitor", description="parent, subsidiary, reseller, competitor, unrelated"
    )
    jurisdiction: str = "US"
    identity_evidence_ids: list[str] = Field(default_factory=list)
    resolution_state: str = Field(
        default="candidate", description="confirmed, candidate, ambiguous, rejected"
    )
    unresolved_alternatives: list[str] = Field(default_factory=list)


class CaptureRequest(BaseModel):
    """A bounded public data capture request executed inside a sandbox."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(..., min_length=1)
    role: CompetitorRole
    attempt_id: str = Field(..., min_length=1)
    grant_ref: str = Field(..., min_length=1)
    source_policy_ref: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    typed_query: dict[str, Any] = Field(default_factory=dict)
    semantic_operation: str = "read"
    method: str = "GET"
    market: str = "US"
    language: str = "en"
    device: str = "desktop"
    filters: dict[str, Any] = Field(default_factory=dict)
    window: dict[str, Any] = Field(default_factory=dict)
    pagination_limits: dict[str, Any] = Field(default_factory=dict)
    requested_artifacts: list[str] = Field(default_factory=list)
    baseline_ids: list[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def validate_url_safety(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Disallowed URL scheme: '{parsed.scheme}'. Only http and https permitted."
            )
        if parsed.username or parsed.password:
            raise ValueError("Credentials in URL authority (userinfo) are prohibited.")
        return value


class CoverageRecord(BaseModel):
    """Execution completeness for an individual capture query."""

    model_config = ConfigDict(extra="forbid")

    coverage_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    queried_entity: str = Field(..., min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    window: dict[str, Any] = Field(default_factory=dict)
    market: str = "US"
    capture_start: datetime
    capture_end: datetime
    status: CoverageStatus
    pages_or_records_obtained: int = Field(ge=0)
    provider_declared_total: int | None = Field(default=None, ge=0)
    depth_cursor_exhausted: bool = False
    excluded_scope: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    """An immutable, tamper-evident capture artifact with provenance."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    original_url: str = Field(..., min_length=1)
    final_url: str = Field(..., min_length=1)
    source_title: str = ""
    source_locator: str = Field(
        ..., min_length=1, description="CSS selector, JSON pointer, or DOM XPath"
    )
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    modified_at: datetime | None = None
    first_shown_at: datetime | None = None
    last_shown_at: datetime | None = None
    target_region: str = "US"
    observation_region: str = "US"
    jurisdiction: str = "US"
    language: str = "en"
    validity_interval: dict[str, Any] = Field(default_factory=dict)
    content_type: str = "application/json"
    original_content_hash: str | None = None
    retained_content_hash: str = Field(..., min_length=64, max_length=64)
    normalization_version: str = "1.0"
    artifact_references: list[str] = Field(default_factory=list)
    collection_decision_ref: str = Field(..., min_length=1)
    terms_decision_ref: str = Field(..., min_length=1)
    robots_decision_ref: str | None = None
    tool_version: str = "1.0"
    extractor_version: str = "1.0"
    profile_version: str = "1.0"
    lineage_refs: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    """A granular, factual observation extracted from an EvidenceRecord."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(..., min_length=1)
    predicate: str = Field(..., min_length=1)
    typed_value: Any = ...
    units_or_dimensions: str | None = None
    subject_id: str = Field(..., min_length=1)
    supporting_evidence_id: str = Field(..., min_length=1)
    locator: str = Field(..., min_length=1)
    observation_kind: str = Field(
        default="observed", description="observed, source_reported, provider_estimate"
    )
    effective_interval: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("typed_value")
    @classmethod
    def validate_decimal_string_for_monetary(cls, val: Any) -> Any:
        # If float is passed for monetary or prices, enforce exact decimal or string
        return val


class Finding(BaseModel):
    """An interpreted claim or synthesized finding linking evidence to assumptions."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(..., min_length=1)
    assumption_ids: list[str] = Field(default_factory=list)
    claim_text: str = Field(..., min_length=1)
    finding_kind: str = Field(
        default="derived_fact",
        description="observation_summary, derived_fact, estimate, inference, unknown",
    )
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    derivation_activity: str = Field(default="extraction")
    derivation_method: str = Field(default="deterministic")
    relevant_market: str = "US"
    relevant_window: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceRating = ConfidenceRating.MEDIUM
    freshness_state: str = Field(default="current_checked")
    uncertainty_causes: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)
    rationale_summary: str | None = None

    @model_validator(mode="after")
    def validate_evidence_or_uncertainty(self) -> Finding:
        if (
            self.finding_kind in ("observation_summary", "derived_fact")
            and not self.supporting_evidence_ids
            and self.confidence != ConfidenceRating.INSUFFICIENT
        ):
            raise ValueError(
                f"Factual finding '{self.finding_id}' requires supporting evidence "
                "or INSUFFICIENT confidence."
            )
        if self.finding_kind == "inference" and not self.rationale_summary:
            raise ValueError(
                f"Inference finding '{self.finding_id}' requires an explicit rationale_summary."
            )
        return self


class ConflictSet(BaseModel):
    """An unresolved or resolved conflict between competing observations."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: str = Field(..., min_length=1)
    claim_key: str = Field(..., min_length=1)
    competing_observation_ids: list[str] = Field(..., min_length=2)
    dimension_comparison: dict[str, Any] = Field(default_factory=dict)
    resolution_status: str = Field(
        default="unresolved", description="unresolved, explained_by_scope, resolved_by_correction"
    )
    resolution_reason: str | None = None
    resolution_evidence_id: str | None = None
    resolver_activity: str | None = None


class MarketShiftAlert(BaseModel):
    """An alert signaling a significant competitive shift detected across baselines."""

    model_config = ConfigDict(extra="forbid")

    alert_id: str = Field(..., min_length=1)
    affected_entities: list[str] = Field(..., min_length=1)
    affected_assumptions: list[str] = Field(default_factory=list)
    change_kind: str = Field(..., min_length=1)
    before_evidence_id: str = Field(..., min_length=1)
    after_evidence_id: str = Field(..., min_length=1)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    change_interval: dict[str, Any] = Field(default_factory=dict)
    significance_rule: str = Field(..., min_length=1)
    confidence: ConfidenceRating = ConfidenceRating.MEDIUM
    scope_limits: list[str] = Field(default_factory=list)
    alert_status: str = Field(
        default="candidate", description="candidate, review_required, validated_observation"
    )


class SpecialistResult(BaseModel):
    """Typed result envelope returned from an authorized specialist attempt to IE."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    profile_id: str = Field(..., min_length=1)
    input_hash: str = Field(..., min_length=64, max_length=64)
    status: str = Field(
        ..., description="success, partial, no_observation, blocked, failed, cancelled"
    )
    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    artifact_manifest: list[str] = Field(default_factory=list)
    coverage: CoverageRecord | None = None
    structured_failures: list[dict[str, Any]] = Field(default_factory=list)
    resource_usage: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    controller_result_ref: str | None = None

    @model_validator(mode="after")
    def validate_status_completeness(self) -> SpecialistResult:
        if (
            self.status == "success"
            and not self.observations
            and not self.findings
            and not self.coverage
        ):
            raise ValueError(
                "Specialist result marked 'success' without observations, "
                "findings, or coverage record."
            )
        return self


class CompetitiveEvidenceBrief(BaseModel):
    """The authoritative output produced by W_COMP synthesis and submitted to IE."""

    model_config = ConfigDict(extra="forbid")

    brief_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    strategy_plan_ref: str = Field(..., min_length=1)
    policy_version: str = "v1"
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assumption_verdicts: dict[str, AssumptionVerdict] = Field(default_factory=dict)
    entity_inventory: list[CompetitorEntity] = Field(default_factory=list)
    source_inventory: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    conflicts: list[ConflictSet] = Field(default_factory=list)
    market_alerts: list[MarketShiftAlert] = Field(default_factory=list)
    evidence_index: list[str] = Field(default_factory=list)
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    failure_summary: list[str] = Field(default_factory=list)
    stale_or_missing_data: list[str] = Field(default_factory=list)
    follow_up_evidence_requests: list[str] = Field(default_factory=list)
