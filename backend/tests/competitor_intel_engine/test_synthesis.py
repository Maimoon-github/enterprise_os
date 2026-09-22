"""Tests for COMP-SYNTH specialist, offline synthesis, deduplication, and conflicts."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.profiles import SYNTHESIS_PROFILE
from app.agents.competitor_intel_engine.subagents.synthesis import (
    CompetitorSynthesisAgent,
    deduplicate_observations,
    detect_conflicts,
    evaluate_assumption_verdicts,
    evaluate_freshness,
    generate_market_alerts,
)
from app.schemas.competitor_intel import (
    AssumptionVerdict,
    CompetitorAttemptInput,
    CompetitorEntity,
    CompetitorResearchContext,
    CompetitorRole,
    Finding,
    Observation,
    SpecialistResult,
    StrategyAssumption,
)
from app.schemas.sandbox import NetworkPolicy


def test_synthesis_offline_only_enforcement():
    """Verify COMP-SYNTH operates strictly offline with NetworkPolicy.DISABLED."""
    agent = CompetitorSynthesisAgent()
    assert agent.role == CompetitorRole.SYNTHESIS
    assert SYNTHESIS_PROFILE.network_policy == NetworkPolicy.DISABLED
    assert "evidence_synthesize" in SYNTHESIS_PROFILE.allowed_operations


def test_deduplication_preserves_independent_observations():
    """Verify deduplication removes true duplicates without collapsing independent observations."""
    # Two identical observations (same predicate, subject, locator, and value)
    obs1 = Observation(
        observation_id="obs-1",
        predicate="product_pricing",
        typed_value={"sku": "pro-tier", "price": "49.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-1",
        locator="json://catalog/pro-tier",
    )
    obs2 = Observation(
        observation_id="obs-2",
        predicate="product_pricing",
        typed_value={"sku": "pro-tier", "price": "49.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-1",
        locator="json://catalog/pro-tier",
    )
    # Third observation has a distinct locator (different store/region)
    obs3 = Observation(
        observation_id="obs-3",
        predicate="product_pricing",
        typed_value={"sku": "pro-tier", "price": "49.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-2",
        locator="json://eu-catalog/pro-tier",
    )

    deduped, dupe_ids = deduplicate_observations([obs1, obs2, obs3])
    assert len(deduped) == 2
    assert dupe_ids == ["obs-2"]
    assert any(o.locator == "json://eu-catalog/pro-tier" for o in deduped)


def test_conflict_preservation_without_voting():
    """Verify competing observations are preserved as unresolved ConflictSets without voting."""
    # Two contradictory prices for identical SKU, currency, and subject
    obs_cheap = Observation(
        observation_id="obs-cheap",
        predicate="product_pricing",
        typed_value={"sku": "flagship-sku", "price": "79.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-page-a",
        locator="dom://pricing-table",
    )
    obs_expensive = Observation(
        observation_id="obs-expensive",
        predicate="product_pricing",
        typed_value={"sku": "flagship-sku", "price": "99.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-page-b",
        locator="dom://checkout-summary",
    )

    conflicts = detect_conflicts([obs_cheap, obs_expensive])
    assert len(conflicts) == 1
    conf = conflicts[0]
    assert conf.resolution_status == "unresolved"
    assert "obs-cheap" in conf.competing_observation_ids
    assert "obs-expensive" in conf.competing_observation_ids
    assert "without voting" in (conf.resolution_reason or "")


def test_freshness_evaluation_flags_stale_observations():
    """Verify observations older than policy threshold are flagged in stale_or_missing_data."""
    now = datetime.now(UTC)
    stale_time = (now - timedelta(hours=48)).isoformat()

    stale_obs = Observation(
        observation_id="obs-stale-price",
        predicate="product_pricing",
        typed_value={"sku": "old-tier", "price": "19.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-old",
        locator="json://old-catalog",
        effective_interval={"start": stale_time},
    )

    fresh_obs = Observation(
        observation_id="obs-fresh-price",
        predicate="product_pricing",
        typed_value={"sku": "new-tier", "price": "29.00", "currency": "USD"},
        subject_id="CompetitorCorp",
        supporting_evidence_id="ev-new",
        locator="json://new-catalog",
        effective_interval={"start": now.isoformat()},
    )

    evaluated, stale_refs = evaluate_freshness([stale_obs, fresh_obs], as_of=now)
    assert len(stale_refs) == 1
    assert "obs-stale-price" in stale_refs[0]


def test_assumption_verdicts_and_market_alerts():
    """Verify assumption verdicts distinguish supported, challenged, mixed, and insufficient."""
    asm_supported = StrategyAssumption(
        id="asm-supp",
        text="Competitor uses subscription pricing model",
        evidence_question="Does competitor offer monthly subscription?",
    )
    asm_challenged = StrategyAssumption(
        id="asm-chal",
        text="Competitor offers free unlimited tier",
        evidence_question="Is free tier unlimited?",
    )
    asm_insufficient = StrategyAssumption(
        id="asm-insuf",
        text="Competitor plans Q4 expansion to APAC",
        evidence_question="Is APAC launch announced?",
    )

    obs = [
        Observation(
            observation_id="obs-sub",
            predicate="product_pricing",
            typed_value={"sku": "sub-monthly", "model": "subscription pricing", "price": "20.00"},
            subject_id="CompetitorCorp",
            supporting_evidence_id="ev-sub",
            locator="dom://pricing",
        )
    ]
    findings = [
        Finding(
            finding_id="find-chal",
            assumption_ids=["asm-chal"],
            claim_text="Competitor tier has hard 5-seat limit; free tier challenged.",
            finding_kind="derived_fact",
            supporting_evidence_ids=["ev-sub"],
        )
    ]

    verdicts, follow_ups = evaluate_assumption_verdicts(
        [asm_supported, asm_challenged, asm_insufficient],
        observations=obs,
        findings=findings,
        conflicts=[],
    )

    assert verdicts["asm-supp"] == AssumptionVerdict.SUPPORTED
    assert verdicts["asm-chal"] == AssumptionVerdict.CHALLENGED
    assert verdicts["asm-insuf"] == AssumptionVerdict.INSUFFICIENT_EVIDENCE
    assert any("asm-insuf" in req for req in follow_ups)

    # Market shift alert generation
    entity = CompetitorEntity(
        entity_id="comp-1",
        names=["CompetitorCorp"],
        domains=["competitor.com"],
    )
    semantic_finding = Finding(
        finding_id="find-shift",
        assumption_ids=["asm-supp"],
        claim_text="Detected semantic_change messaging change from baseline positioning.",
        finding_kind="derived_fact",
        supporting_evidence_ids=["ev-sub-before", "ev-sub-after"],
    )
    alerts = generate_market_alerts([semantic_finding], conflicts=[], entities=[entity])
    assert len(alerts) == 1
    assert alerts[0].change_kind == "positioning_or_commercial_shift"
    assert alerts[0].before_evidence_id == "ev-sub-before"
    assert alerts[0].after_evidence_id == "ev-sub-after"


@pytest.mark.asyncio
async def test_synthesis_agent_execute_attempt():
    """Verify execute_synthesis_attempt outputs schema-valid SpecialistResult and Brief."""
    agent = CompetitorSynthesisAgent()
    context = CompetitorResearchContext(
        task_id="task-synth-1",
        tenant_id="tenant-alpha",
        run_id="run-synth-001",
        brand_id="brand-1",
        strategy_plan_ref="plan-v1",
        strategy_plan_hash="a" * 64,
        assumptions=[
            StrategyAssumption(
                id="asm-1",
                text="Competitor has annual billing discount",
                evidence_question="Is annual discount offered?",
            )
        ],
        scoped_entities=["CompetitorCorp"],
    )

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-synth-1",
        task_id="task-synth-1",
        tenant_id="tenant-alpha",
        run_id="run-synth-001",
        step_id="step-synth-1",
        attempt_id="att-synth-001",
        role=CompetitorRole.SYNTHESIS,
        profile_id="w_comp.synthesis.v1",
        llm_instance_id="llm-synth-001",
        approved_operation_ids=["evidence_synthesize"],
        context_slice={},
        input_hash="e" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    mock_spec_result = SpecialistResult(
        step_id="step-price-1",
        attempt_id="att-price-001",
        profile_id="w_comp.price.v1",
        input_hash="f" * 64,
        status="success",
        observations=[
            Observation(
                observation_id="obs-annual",
                predicate="product_pricing",
                typed_value={"billing": "annual discount", "price": "180.00"},
                subject_id="CompetitorCorp",
                supporting_evidence_id="ev-p1",
                locator="json://pricing",
            )
        ],
    )

    spec_res, brief = await agent.execute_synthesis_attempt(
        attempt_input=attempt_input,
        context=context,
        specialist_results=[mock_spec_result],
    )

    assert spec_res.status == "success"
    assert brief.run_id == "run-synth-001"
    assert "asm-1" in brief.assumption_verdicts
    assert brief.assumption_verdicts["asm-1"] == AssumptionVerdict.SUPPORTED
