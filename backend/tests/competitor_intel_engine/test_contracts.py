"""Tests for Competitor Intel Engine domain and evidence contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.competitor_intel import (
    CaptureRequest,
    CompetitorAttemptInput,
    CompetitorResearchContext,
    CompetitorRole,
    ConfidenceRating,
    CoverageRecord,
    CoverageStatus,
    Finding,
    ResearchStepProposal,
    SpecialistResult,
    StepProposalItem,
    StrategyAssumption,
)


def test_competitor_research_context_validation_and_hash():
    """Verify CompetitorResearchContext enforces hash calculation and required bindings."""
    assumption = StrategyAssumption(
        id="asm-1",
        text="Competitor is discounting pricing in Q3",
        evidence_question="What is the average promo discount on flagship SKU?",
    )
    ctx = CompetitorResearchContext(
        task_id="task-100",
        tenant_id="tenant-alpha",
        run_id="run-001",
        brand_id="brand-omega",
        strategy_plan_ref="strat-plan-v1",
        strategy_plan_hash="a" * 64,
        assumptions=[assumption],
        scoped_entities=["CompetitorCorp"],
    )
    digest = ctx.compute_context_hash()
    assert len(digest) == 64

    # Reject unknown privilege fields
    extra_data = {
        "task_id": "task-100",
        "tenant_id": "tenant-alpha",
        "run_id": "run-001",
        "brand_id": "brand-omega",
        "strategy_plan_ref": "strat-plan-v1",
        "strategy_plan_hash": "a" * 64,
        "assumptions": [assumption],
        "grant_elevation": "superadmin",  # forbidden
    }
    with pytest.raises(ValidationError):
        CompetitorResearchContext.model_validate(extra_data)


def test_step_proposal_item_cannot_assign_coordinator_as_specialist():
    """Verify coordinator W_COMP cannot be assigned specialist execution steps."""
    with pytest.raises(ValidationError, match="Coordinator W_COMP cannot execute specialist steps"):
        StepProposalItem(
            step_id="step-1",
            role=CompetitorRole.COORDINATOR,
            target_entity="CompetitorCorp",
        )


def test_research_step_proposal_rejects_dangling_dependencies():
    """Verify proposal validates topological dependency consistency."""
    item1 = StepProposalItem(
        step_id="step-disc",
        role=CompetitorRole.DISCOVERY,
        target_entity="CompetitorCorp",
    )
    item2 = StepProposalItem(
        step_id="step-price",
        role=CompetitorRole.PRICE,
        dependencies=["non-existent-step"],
    )
    with pytest.raises(ValidationError, match="Dangling dependency"):
        ResearchStepProposal(
            proposal_id="prop-1",
            input_hash="b" * 64,
            ordered_steps=[item1, item2],
        )


def test_attempt_input_cannot_target_coordinator():
    """Verify CompetitorAttemptInput rejects W_COMP coordinator role."""
    with pytest.raises(
        ValidationError, match="W_COMP coordinator cannot receive sandbox attempt input"
    ):
        CompetitorAttemptInput(
            grant_id="grant-1",
            task_id="task-1",
            tenant_id="tenant-1",
            run_id="run-1",
            step_id="step-1",
            attempt_id="att-1",
            role=CompetitorRole.COORDINATOR,
            profile_id="w_comp.coordinator.v1",
            llm_instance_id="llm-1",
            approved_operation_ids=["op1"],
            input_hash="c" * 64,
            deadline=datetime.now(UTC) + timedelta(minutes=5),
        )


def test_capture_request_url_safety():
    """Verify URL validation rejects non-HTTP schemes and embedded credentials."""
    # Disallow file/ftp/etc.
    with pytest.raises(ValidationError, match="Disallowed URL scheme"):
        CaptureRequest(
            request_id="req-1",
            role=CompetitorRole.DISCOVERY,
            attempt_id="att-1",
            grant_ref="grant-1",
            source_policy_ref="pol-1",
            url="file:///etc/passwd",
        )

    # Disallow userinfo
    with pytest.raises(ValidationError, match="userinfo"):
        CaptureRequest(
            request_id="req-1",
            role=CompetitorRole.DISCOVERY,
            attempt_id="att-1",
            grant_ref="grant-1",
            source_policy_ref="pol-1",
            url="https://admin:secret@competitor.com/prices",
        )


def test_finding_requires_evidence_or_insufficient_confidence():
    """Verify factual findings require supporting evidence or explicit INSUFFICIENT confidence."""
    # Factual claim without evidence and medium confidence must fail
    with pytest.raises(ValidationError, match="requires supporting evidence"):
        Finding(
            finding_id="find-1",
            claim_text="Competitor dropped price by 20%",
            finding_kind="derived_fact",
            confidence=ConfidenceRating.MEDIUM,
            supporting_evidence_ids=[],
        )

    # Inconclusive/insufficient finding without evidence is valid
    f = Finding(
        finding_id="find-2",
        claim_text="Competitor dropped price by 20%",
        finding_kind="derived_fact",
        confidence=ConfidenceRating.INSUFFICIENT,
        supporting_evidence_ids=[],
    )
    assert f.confidence == ConfidenceRating.INSUFFICIENT

    # Inference requires rationale summary
    with pytest.raises(ValidationError, match="requires an explicit rationale_summary"):
        Finding(
            finding_id="find-3",
            claim_text="Competitor planning European expansion",
            finding_kind="inference",
            confidence=ConfidenceRating.LOW,
            supporting_evidence_ids=["ev-1"],
            rationale_summary=None,
        )


def test_specialist_result_validation():
    """Verify SpecialistResult validates completion integrity."""
    # Success status cannot be empty
    with pytest.raises(ValidationError, match="without observations, findings, or coverage record"):
        SpecialistResult(
            step_id="step-1",
            attempt_id="att-1",
            profile_id="w_comp.price.v1",
            input_hash="d" * 64,
            status="success",
            observations=[],
            findings=[],
            coverage=None,
        )

    # Partial status with coverage is valid
    coverage = CoverageRecord(
        coverage_id="cov-1",
        source_id="src-meta",
        queried_entity="CompetitorCorp",
        capture_start=datetime.now(UTC),
        capture_end=datetime.now(UTC),
        status=CoverageStatus.PARTIAL,
        pages_or_records_obtained=5,
        limitations=["Rate limit exceeded at page 2"],
    )
    res = SpecialistResult(
        step_id="step-1",
        attempt_id="att-1",
        profile_id="w_comp.ads.v1",
        input_hash="d" * 64,
        status="partial",
        coverage=coverage,
    )
    assert res.status == "partial"
