"""Tests for Learning & Performance Engine versioned contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError

from app.schemas.learning_performance import (
    CalibrationProposal,
    EvidenceCategory,
    LearningAttemptInput,
    LearningDatasetManifest,
    LearningDeltaCandidate,
    LearningEstimate,
    LearningQAResult,
    LearningSpecialistResult,
    LearningTaskInput,
    LearningUncertainty,
    QADecision,
    SpecialistStatus,
    UncertaintyKind,
)


def test_learning_uncertainty_finite_and_bounds() -> None:
    u = LearningUncertainty(
        kind=UncertaintyKind.CONFIDENCE_INTERVAL,
        lower_bound=0.1,
        upper_bound=0.5,
        level=0.95,
    )
    assert u.lower_bound == 0.1
    assert u.upper_bound == 0.5

    # Inverted bounds fail
    with pytest.raises(ValidationError, match="lower_bound .* cannot exceed upper_bound"):
        LearningUncertainty(
            kind=UncertaintyKind.CONFIDENCE_INTERVAL,
            lower_bound=0.6,
            upper_bound=0.2,
        )

    # NaN / Inf bounds fail
    with pytest.raises(ValidationError, match="must be finite"):
        LearningUncertainty(
            kind=UncertaintyKind.CONFIDENCE_INTERVAL,
            lower_bound=float("nan"),
            upper_bound=0.5,
        )

    # Unavailable kind requires reason
    with pytest.raises(ValidationError, match="reason_unavailable is required"):
        LearningUncertainty(kind=UncertaintyKind.UNAVAILABLE)


def test_learning_estimate_observational_cannot_claim_causal() -> None:
    unc = LearningUncertainty(kind=UncertaintyKind.CONFIDENCE_INTERVAL, lower_bound=1.2, upper_bound=2.4)
    # Observational claiming causal must fail
    with pytest.raises(ValidationError, match="Observational evidence cannot permit causal claims"):
        LearningEstimate(
            estimate_id="est-1",
            metric="roas",
            estimand="channel_roas",
            evidence_category=EvidenceCategory.OBSERVATIONAL,
            tenant_id="tenant-1",
            method_name="linear_attribution",
            point_estimate=1.8,
            uncertainty=unc,
            causal_claim_permitted=True,
        )

    # Valid observational estimate
    valid = LearningEstimate(
        estimate_id="est-1",
        metric="roas",
        estimand="channel_roas",
        evidence_category=EvidenceCategory.OBSERVATIONAL,
        tenant_id="tenant-1",
        method_name="linear_attribution",
        point_estimate=1.8,
        uncertainty=unc,
        causal_claim_permitted=False,
    )
    assert valid.causal_claim_permitted is False


def test_calibration_proposal_cannot_be_applied_same_run() -> None:
    unc = LearningUncertainty(kind=UncertaintyKind.CONFIDENCE_INTERVAL, lower_bound=0.05, upper_bound=0.15)
    now = datetime.now(UTC)

    # Applied proposal in same run must fail
    with pytest.raises(ValidationError, match="New calibration proposals must have applied=False"):
        CalibrationProposal(
            proposal_id="cal-1",
            tenant_id="tenant-1",
            source_experiment_id="exp-101",
            qa_evidence_ref="qa-digest-1",
            source_estimand="itt_lift",
            target_estimand="prior_mean",
            channel="meta",
            target_model_version="mmm-v1",
            proposed_weight_or_multiplier=0.10,
            uncertainty=unc,
            transport_rationale="Matched audience and spend regime",
            applicability_window_start=now,
            applicability_window_end=now + timedelta(days=30),
            applied=True,
        )


def test_specialist_result_insufficient_evidence_forbids_fabricated_metrics() -> None:
    # Insufficient evidence with fabricated point estimate must fail
    unc = LearningUncertainty(kind=UncertaintyKind.UNAVAILABLE, reason_unavailable="Zero experimental holdouts")
    fabricated_est = LearningEstimate(
        estimate_id="est-2",
        metric="lift",
        estimand="itt",
        evidence_category=EvidenceCategory.EXPERIMENTAL,
        tenant_id="tenant-1",
        method_name="holdout",
        point_estimate=0.15,
        uncertainty=unc,
    )

    with pytest.raises(ValidationError, match="Cannot fabricate point estimates when status is INSUFFICIENT_EVIDENCE"):
        LearningSpecialistResult(
            role="LEARN-INCREMENTALITY",
            specialist_profile_id="learn.incrementality.v1",
            attempt_id="att-1",
            dataset_version="ds-v1",
            status=SpecialistStatus.INSUFFICIENT_EVIDENCE,
            estimates=[fabricated_est],
            insufficient_evidence_reason="Holdout count is zero",
        )


def test_learning_delta_candidate_status_enforcement() -> None:
    now = datetime.now(UTC)
    unc = LearningUncertainty(kind=UncertaintyKind.CONFIDENCE_INTERVAL, lower_bound=0.1, upper_bound=0.2)

    # Worker proposing status='promoted' directly must fail closed
    with pytest.raises(ValidationError, match="W_LEARN may only propose status='candidate'"):
        LearningDeltaCandidate(
            candidate_id="cand-1",
            idempotency_key="key-1",
            tenant_id="tenant-1",
            base_memory_version="mem-v1",
            uncertainty=unc,
            qa_digest="qa-hash",
            applicable_window_start=now,
            applicable_window_end=now + timedelta(days=14),
            status="promoted",
        )
