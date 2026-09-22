"""Tests for Competitor Intel Engine runtime execution and recovery (COMP-03)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.competitor_intel import CompetitorIntelAgent
from app.agents.competitor_intel_engine.profiles import dispatch_competitor_specialist_attempt
from app.schemas.competitor_intel import (
    AssumptionVerdict,
    CompetitiveEvidenceBrief,
    CompetitorAttemptInput,
    CompetitorResearchContext,
    CompetitorRole,
    StrategyAssumption,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_coordinator_plan_interpretation_and_brief_validation():
    """Verify W_COMP coordinator decomposes strategy plan into bounded DAG without sandbox."""
    agent = CompetitorIntelAgent()

    assumption = StrategyAssumption(
        id="asm-brand-1",
        text="Competitor is shifting ad spend to TikTok in US",
        evidence_question="What is the proportion of active ads on TikTok vs Meta?",
    )
    context = CompetitorResearchContext(
        task_id="task-001",
        tenant_id="tenant-alpha",
        run_id="run-9999",
        brand_id="brand-omega",
        strategy_plan_ref="strat-v1",
        strategy_plan_hash="e" * 64,
        assumptions=[assumption],
        scoped_entities=["CompetitorCorp"],
    )

    proposal = agent.interpret_strategy_plan(context)
    assert proposal.proposal_id == "prop-run-9999"
    assert len(proposal.ordered_steps) == 6

    # Verify DAG ordering: discovery is prerequisite for domain steps;
    # all domain steps are prerequisites for synthesis
    step_map = {s.role: s for s in proposal.ordered_steps}
    disc_step = step_map[CompetitorRole.DISCOVERY]
    synth_step = step_map[CompetitorRole.SYNTHESIS]

    assert disc_step.dependencies == []
    assert disc_step.step_id in step_map[CompetitorRole.ADS].dependencies
    assert disc_step.step_id in step_map[CompetitorRole.PRICE].dependencies
    assert disc_step.step_id in step_map[CompetitorRole.SEARCH].dependencies
    assert disc_step.step_id in step_map[CompetitorRole.POSITION].dependencies

    assert step_map[CompetitorRole.ADS].step_id in synth_step.dependencies
    assert step_map[CompetitorRole.PRICE].step_id in synth_step.dependencies

    # Brief validation without sandbox
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-001",
        run_id="run-9999",
        strategy_plan_ref="strat-v1",
        assumption_verdicts={"asm-brand-1": AssumptionVerdict.SUPPORTED},
    )
    val_result = agent.validate_synthesis_brief(brief, context)
    assert val_result["valid"] is True
    assert val_result["missing_assumptions"] == []


@pytest.mark.asyncio
async def test_specialist_execution_dispatch_roundtrip():
    """Verify authorized specialist attempt executes through sandbox client wrapper."""

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {
                    "benchmark_price": "39.99",
                    "competitor": "CompetitorCorp",
                }
                execution_id = "exec-mock-001"

            return MockResult()

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-001",
        task_id="task-001",
        tenant_id="tenant-alpha",
        run_id="run-9999",
        step_id="step-price-1",
        attempt_id="att-001",
        role=CompetitorRole.PRICE,
        profile_id="w_comp.price.v1",
        llm_instance_id="llm-price-001",
        approved_operation_ids=["price_extract_compare"],
        input_hash="f" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-001",
        specialist_id="COMP-PRICE",
        allowed_domains=["competitor.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res = await dispatch_competitor_specialist_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
    )

    assert res.status == "success"
    assert len(res.observations) == 1
    assert res.observations[0].predicate == "benchmark_price"
    assert res.observations[0].typed_value == "39.99"
    assert res.lineage["attempt_id"] == "att-001"
