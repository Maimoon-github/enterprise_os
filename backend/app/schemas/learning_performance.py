"""Versioned, immutable data contracts for W_LEARN and its measurement specialists."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LearningWorkflowStage(StrEnum):
    """Execution stages in the W_LEARN fixed DAG."""

    TELEMETRY = "telemetry"
    ATTRIBUTION = "attribution"
    INCREMENTALITY = "incrementality"
    FATIGUE = "fatigue"
    DECAY = "decay"
    QA = "qa"
    SYNTHESIS = "synthesis"


class EvidenceCategory(StrEnum):
    """Methodological inference category for measurement claims."""

    OBSERVATIONAL = "observational"
    MODEL_BASED = "model_based"
    QUASI_EXPERIMENTAL = "quasi_experimental"
    EXPERIMENTAL = "experimental"


class UncertaintyKind(StrEnum):
    """Statistical typology of uncertainty estimates."""

    CONFIDENCE_INTERVAL = "confidence_interval"
    CREDIBLE_INTERVAL = "credible_interval"
    SENSITIVITY_RANGE = "sensitivity_range"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class SpecialistStatus(StrEnum):
    """Terminal outcome status of a specialist execution attempt."""

    COMPLETE = "COMPLETE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


class QADecision(StrEnum):
    """Deterministic decision emitted by LEARN-QA."""

    PASS = "PASS"
    REVISE = "REVISE"
    BLOCK = "BLOCK"


def _check_finite(val: float | None, field_name: str) -> None:
    if val is not None and (math.isnan(val) or math.isinf(val)):
        raise ValueError(f"Field '{field_name}' must be finite, got {val}")


class LearningUncertainty(BaseModel):
    """Explicit uncertainty quantification for estimates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: UncertaintyKind
    method: str | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    level: float | None = Field(default=None, ge=0.0, le=1.0)
    sampling_unit: str | None = None
    limitations: list[str] = Field(default_factory=list)
    reason_unavailable: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> LearningUncertainty:
        _check_finite(self.lower_bound, "lower_bound")
        _check_finite(self.upper_bound, "upper_bound")
        if self.lower_bound is not None and self.upper_bound is not None:
            if self.lower_bound > self.upper_bound:
                raise ValueError(
                    f"lower_bound ({self.lower_bound}) cannot exceed upper_bound ({self.upper_bound})"
                )
        if self.kind == UncertaintyKind.UNAVAILABLE and not self.reason_unavailable:
            raise ValueError("reason_unavailable is required when uncertainty kind is UNAVAILABLE")
        return self


class LearningEstimate(BaseModel):
    """Strongly-typed measurement estimate produced by an analytical specialist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimate_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    estimand: str = Field(min_length=1)
    evidence_category: EvidenceCategory
    tenant_id: str = Field(min_length=1)
    brand_id: str | None = None
    channel: str | None = None
    cohort: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    method_name: str = Field(min_length=1)
    method_version: str = "1.0"
    point_estimate: float | None = None
    units: str = "ratio"
    currency: str | None = None
    uncertainty: LearningUncertainty
    evidence_refs: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    is_extrapolated: bool = False
    causal_claim_permitted: bool = False

    @model_validator(mode="after")
    def validate_estimate(self) -> LearningEstimate:
        _check_finite(self.point_estimate, "point_estimate")
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise ValueError("window_start cannot be after window_end")
        if (
            self.evidence_category == EvidenceCategory.OBSERVATIONAL
            and self.causal_claim_permitted
        ):
            raise ValueError(
                "Observational evidence cannot permit causal claims; must be labeled strictly observational."
            )
        return self


class LearningTaskInput(BaseModel):
    """Task-level intake envelope authorized by IE for W_LEARN."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0"
    task_id: str = Field(min_length=1)
    grant_reference: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    brand_id: str | None = None
    channels: list[str] = Field(default_factory=list)
    cohort: str | None = None
    window_start: datetime
    window_end: datetime
    allowed_lookback_days: int = Field(default=30, ge=0)
    conversion_maturity_as_of: datetime | None = None
    dataset_references: list[str] = Field(default_factory=list)
    kpi_dictionary_version: str = "1.0"
    method_plan_version: str = "1.0"
    qa_policy_version: str = "1.0"
    retry_budget: int = Field(default=3, ge=1)
    resource_limits: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_window(self) -> LearningTaskInput:
        if self.window_start > self.window_end:
            raise ValueError("window_start cannot be after window_end")
        return self


class LearningDatasetManifest(BaseModel):
    """Immutable normalized dataset manifest produced by LEARN-TELEMETRY."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    version: str = "1.0"
    source_references: list[str] = Field(default_factory=list)
    snapshot_time: datetime
    event_time_meaning: str = "event_occurred_at"
    timezone: str = "UTC"
    grain: str = "event"
    authorized_window_start: datetime
    authorized_window_end: datetime
    identity_coverage: float = Field(ge=0.0, le=1.0)
    row_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    quarantine_count: int = Field(ge=0)
    missingness_summary: dict[str, float] = Field(default_factory=dict)
    kpi_definitions: dict[str, str] = Field(default_factory=dict)
    currencies: list[str] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)
    readiness_by_method: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_window(self) -> LearningDatasetManifest:
        if self.authorized_window_start > self.authorized_window_end:
            raise ValueError("authorized_window_start cannot be after authorized_window_end")
        return self


class LearningAttemptInput(BaseModel):
    """Scoped mandate for a single specialist attempt inside S_ATTR."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specialist_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = "1.0"
    attempt_id: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    expires_at: datetime
    operation: str = Field(min_length=1)
    input_hashes: dict[str, str] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    method_version: str = "1.0"
    runtime_policy_ref: str = "policy:w_learn:specialist:v1"
    resource_budget: dict[str, Any] = Field(default_factory=dict)


class CalibrationProposal(BaseModel):
    """Calibration prior proposal emitted by LEARN-INCREMENTALITY for a future run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    brand_id: str | None = None
    source_experiment_id: str = Field(min_length=1)
    source_experiment_version: str = "1.0"
    qa_evidence_ref: str = Field(min_length=1)
    source_estimand: str = Field(min_length=1)
    target_estimand: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    cohort: str | None = None
    target_model_version: str = Field(min_length=1)
    distribution_type: str = "gaussian_prior"
    proposed_weight_or_multiplier: float
    uncertainty: LearningUncertainty
    transport_rationale: str = Field(min_length=1)
    overlap_and_prior_use_ledger: list[str] = Field(default_factory=list)
    applicability_window_start: datetime
    applicability_window_end: datetime
    limitations: list[str] = Field(default_factory=list)
    applied: bool = False

    @model_validator(mode="after")
    def validate_proposal(self) -> CalibrationProposal:
        _check_finite(self.proposed_weight_or_multiplier, "proposed_weight_or_multiplier")
        if self.applied:
            raise ValueError(
                "New calibration proposals must have applied=False; cannot be applied in the same run."
            )
        if self.applicability_window_start > self.applicability_window_end:
            raise ValueError("applicability_window_start cannot be after applicability_window_end")
        return self


class LearningSpecialistResult(BaseModel):
    """Terminal typed result of an analytical specialist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1)
    specialist_profile_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    status: SpecialistStatus
    estimates: list[LearningEstimate] = Field(default_factory=list)
    diagnostic_refs: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    error_category: str | None = None
    insufficient_evidence_reason: str | None = None

    @model_validator(mode="after")
    def validate_specialist_result(self) -> LearningSpecialistResult:
        if self.status == SpecialistStatus.INSUFFICIENT_EVIDENCE:
            if not self.insufficient_evidence_reason:
                raise ValueError("insufficient_evidence_reason required when status is INSUFFICIENT_EVIDENCE")
            for est in self.estimates:
                if est.point_estimate is not None:
                    raise ValueError(
                        "Cannot fabricate point estimates when status is INSUFFICIENT_EVIDENCE."
                    )
        elif self.status == SpecialistStatus.FAILED:
            if not self.error_category:
                raise ValueError("error_category is required when specialist status is FAILED")
        return self


class LearningQAResult(BaseModel):
    """Deterministic quality decision and claim allowlist produced by LEARN-QA."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: QADecision
    input_bundle_digest: str = Field(min_length=1)
    qa_profile_id: str = Field(min_length=1)
    qa_attempt_id: str = Field(min_length=1)
    deterministic_gate_results: dict[str, bool] = Field(default_factory=dict)
    issue_codes: list[str] = Field(default_factory=list)
    accepted_claim_ids: list[str] = Field(default_factory=list)
    rejected_claim_ids: list[str] = Field(default_factory=list)
    remediation_requests: list[str] = Field(default_factory=list)
    evidence_bundle_digest: str = Field(min_length=1)
    provenance_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_qa_result(self) -> LearningQAResult:
        if self.decision == QADecision.BLOCK and not self.issue_codes:
            raise ValueError("Blocked QA result must enumerate issue codes.")
        if self.decision == QADecision.PASS and self.rejected_claim_ids and not self.accepted_claim_ids:
            raise ValueError("PASS decision cannot have zero accepted claims when rejections exist.")
        return self


class LearningDeltaCandidate(BaseModel):
    """Validated candidate learning delta synthesized by W_LEARN for IE promotion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    brand_id: str | None = None
    base_memory_version: str = Field(min_length=1)
    accepted_claim_ids: list[str] = Field(default_factory=list)
    scoped_metrics: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    uncertainty: LearningUncertainty
    qa_digest: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    applicable_window_start: datetime
    applicable_window_end: datetime
    proposed_update_kind: str = "performance_heuristic"
    status: str = "candidate"

    @model_validator(mode="after")
    def validate_candidate(self) -> LearningDeltaCandidate:
        if self.status != "candidate":
            raise ValueError(
                f"W_LEARN may only propose status='candidate'; status '{self.status}' violates Model A promotion authority."
            )
        if self.applicable_window_start > self.applicable_window_end:
            raise ValueError("applicable_window_start cannot be after applicable_window_end")
        for k, v in self.scoped_metrics.items():
            _check_finite(v, f"scoped_metrics[{k}]")
        return self
