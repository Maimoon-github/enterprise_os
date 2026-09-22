"""End-to-end tests for W_COMP validation, IE final acceptance, provenance, and HITL handoff."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.competitor_intel_engine.competitor_intel import CompetitorIntelAgent
from app.core.exceptions import PolicyViolationError
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.schemas.competitor_intel import (
    AssumptionVerdict,
    CompetitiveEvidenceBrief,
    CompetitorEntity,
    CompetitorResearchContext,
    ConflictSet,
    MarketShiftAlert,
    Observation,
    StrategyAssumption,
)
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus


@pytest.fixture
def mock_ie():
    """Create an IntelligenceEngine with mocked dependencies."""
    llm_client = MagicMock()
    context_assembler = MagicMock()
    policy_evaluator = MagicMock()
    dag_scheduler = MagicMock()
    task_state_machine = MagicMock()
    evidence_synthesizer = MagicMock()
    hitl_preview_generator = MagicMock()
    hitl_coordinator = MagicMock()
    provenance_recorder = AsyncMock()
    mcp_host = MagicMock()

    ie = IntelligenceEngine(
        policy_evaluator=policy_evaluator,
        dag_scheduler=dag_scheduler,
        task_state_machine=task_state_machine,
        context_assembler=context_assembler,
        evidence_synthesizer=evidence_synthesizer,
        hitl_preview_generator=hitl_preview_generator,
        hitl_coordinator=hitl_coordinator,
        provenance_recorder=provenance_recorder,
        mcp_host=mcp_host,
        workers={},
        llm_client=llm_client,
    )
    return ie


def test_w_comp_validates_brief_completeness():
    """Verify W_COMP coordinator checks assumption coverage and validates brief schema only."""
    agent = CompetitorIntelAgent()
    context = CompetitorResearchContext(
        task_id="task-1",
        tenant_id="tenant-alpha",
        run_id="run-001",
        brand_id="brand-1",
        strategy_plan_ref="plan-v1",
        strategy_plan_hash="a" * 64,
        assumptions=[
            StrategyAssumption(
                id="asm-1",
                text="Competitor is discounting pricing in Q3",
                evidence_question="Discount percentage?",
            ),
            StrategyAssumption(
                id="asm-2",
                text="Competitor has annual billing plan",
                evidence_question="Is annual available?",
            ),
        ],
        scoped_entities=["CompetitorCorp"],
    )

    # Incomplete brief (missing verdict for asm-2)
    incomplete_brief = CompetitiveEvidenceBrief(
        brief_id="brief-001",
        run_id="run-001",
        strategy_plan_ref="plan-v1",
        assumption_verdicts={"asm-1": AssumptionVerdict.SUPPORTED},
        entity_inventory=[],
        source_inventory=[],
        observations=[],
        findings=[],
        conflicts=[],
        market_alerts=[],
    )

    val_incomplete = agent.validate_synthesis_brief(incomplete_brief, context)
    assert val_incomplete["valid"] is False
    assert "asm-2" in val_incomplete["missing_assumptions"]

    # Complete brief
    complete_brief = CompetitiveEvidenceBrief(
        brief_id="brief-002",
        run_id="run-001",
        strategy_plan_ref="plan-v1",
        assumption_verdicts={
            "asm-1": AssumptionVerdict.SUPPORTED,
            "asm-2": AssumptionVerdict.SUPPORTED,
        },
        entity_inventory=[],
        source_inventory=[],
        observations=[],
        findings=[],
        conflicts=[],
        market_alerts=[],
    )

    val_complete = agent.validate_synthesis_brief(complete_brief, context)
    assert val_complete["valid"] is True
    assert len(val_complete["missing_assumptions"]) == 0


@pytest.mark.asyncio
async def test_ie_accepts_valid_brief_and_commits_state(mock_ie):
    """Verify IE accepts validated brief, transitions task to COMPLETED, and records provenance."""
    directive = Directive(
        directive_id="dir-1",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-1"]),
        objective="Analyze competitors",
        budget_cap=1000.0,
    )
    task = CanonicalTaskState(
        task_id="task-comp-1",
        directive_id="dir-1",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.IN_PROGRESS,
    )
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-valid-1",
        run_id="run-001",
        strategy_plan_ref="plan-v1",
        assumption_verdicts={"asm-1": AssumptionVerdict.SUPPORTED},
        entity_inventory=[
            CompetitorEntity(
                entity_id="comp-1",
                names=["CompetitorCorp"],
                domains=["competitor.com"],
            )
        ],
        source_inventory=["json://pricing"],
        observations=[
            Observation(
                observation_id="obs-1",
                predicate="product_pricing",
                typed_value={"sku": "s1", "price": "10.00"},
                subject_id="CompetitorCorp",
                supporting_evidence_id="ev-1",
                locator="json://pricing",
            )
        ],
        findings=[],
        conflicts=[],
        market_alerts=[],
    )

    validation_report = {"valid": True, "missing_assumptions": []}
    mock_artifact_repo = AsyncMock()

    mock_ie._task_state_machine.transition.return_value = CanonicalTaskState(
        task_id="task-comp-1",
        directive_id="dir-1",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.COMPLETED,
    )

    result = await mock_ie.accept_competitive_evidence_brief(
        directive=directive,
        task=task,
        brief=brief,
        validation_report=validation_report,
        artifact_repo=mock_artifact_repo,
    )

    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"
    assert result["requires_hitl"] is False
    assert task.status == TaskStatus.COMPLETED

    # Provenance recorded
    mock_ie._provenance_recorder.record.assert_called_once()
    call_kwargs = mock_ie._provenance_recorder.record.call_args.kwargs
    assert call_kwargs["activity"] == "competitor_evidence_synthesis"
    assert call_kwargs["agent"] == "COMP-SYNTH"

    # Artifact registered
    mock_artifact_repo.register.assert_called_once()


@pytest.mark.asyncio
async def test_ie_routes_conflicts_and_market_alerts_to_hitl(mock_ie):
    """Verify IE flags briefs with conflicts or market shift alerts for HITL review (HELD)."""
    directive = Directive(
        directive_id="dir-2",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-1"]),
        objective="Analyze pricing shifts",
        budget_cap=1000.0,
    )
    task = CanonicalTaskState(
        task_id="task-comp-2",
        directive_id="dir-2",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.IN_PROGRESS,
    )
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-conflict-1",
        run_id="run-002",
        strategy_plan_ref="plan-v1",
        assumption_verdicts={"asm-1": AssumptionVerdict.MIXED},
        conflicts=[
            ConflictSet(
                conflict_id="conf-1",
                claim_key="CompetitorCorp::sku1::USD",
                competing_observation_ids=["obs-1", "obs-2"],
                dimension_comparison={"competing_prices": ["10.00", "20.00"]},
                resolution_status="unresolved",
            )
        ],
        market_alerts=[
            MarketShiftAlert(
                alert_id="alert-1",
                affected_entities=["CompetitorCorp"],
                affected_assumptions=["asm-1"],
                change_kind="commercial_shift",
                before_evidence_id="ev-1",
                after_evidence_id="ev-2",
                significance_rule="rule.v1",
            )
        ],
    )

    validation_report = {"valid": True, "missing_assumptions": []}

    mock_ie._task_state_machine.transition.return_value = CanonicalTaskState(
        task_id="task-comp-2",
        directive_id="dir-2",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.HELD,
    )

    result = await mock_ie.accept_competitive_evidence_brief(
        directive=directive,
        task=task,
        brief=brief,
        validation_report=validation_report,
    )

    assert result["accepted"] is True
    assert result["requires_hitl"] is True
    assert task.status == TaskStatus.HELD


@pytest.mark.asyncio
async def test_ie_bounded_single_recheck_round(mock_ie):
    """Verify IE authorizes at most one bounded recheck round for follow-up evidence requests."""
    directive = Directive(
        directive_id="dir-3",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-1"]),
        objective="Recheck missing data",
        budget_cap=1000.0,
    )
    task = CanonicalTaskState(
        task_id="task-comp-3",
        directive_id="dir-3",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.IN_PROGRESS,
    )
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-recheck-1",
        run_id="run-003",
        strategy_plan_ref="plan-v1",
        assumption_verdicts={"asm-1": AssumptionVerdict.INSUFFICIENT_EVIDENCE},
        follow_up_evidence_requests=["Recheck price point on official catalog"],
    )

    validation_report = {"valid": True, "missing_assumptions": []}

    # Round 0: Recheck authorized
    res_round0 = await mock_ie.accept_competitive_evidence_brief(
        directive=directive,
        task=task,
        brief=brief,
        validation_report=validation_report,
        recheck_round_count=0,
    )
    assert res_round0["accepted"] is False
    assert res_round0["status"] == "RECHECK_AUTHORIZED"
    assert res_round0["recheck_round"] == 1

    # Round 1: Recheck limit exhausted -> Proceed to acceptance
    mock_ie._task_state_machine.transition.return_value = CanonicalTaskState(
        task_id="task-comp-3",
        directive_id="dir-3",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.COMPLETED,
    )
    res_round1 = await mock_ie.accept_competitive_evidence_brief(
        directive=directive,
        task=task,
        brief=brief,
        validation_report=validation_report,
        recheck_round_count=1,
    )
    assert res_round1["accepted"] is True
    assert res_round1["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_ie_rejects_unvalidated_brief(mock_ie):
    """Verify IE rejects brief when W_COMP validation report indicates invalidity."""
    directive = Directive(
        directive_id="dir-4",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-1"]),
        objective="Invalid test",
        budget_cap=1000.0,
    )
    task = CanonicalTaskState(
        task_id="task-comp-4",
        directive_id="dir-4",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        status=TaskStatus.IN_PROGRESS,
    )
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-invalid-1",
        run_id="run-004",
        strategy_plan_ref="plan-v1",
    )
    invalid_report = {"valid": False, "missing_assumptions": ["asm-crit"]}

    with pytest.raises(PolicyViolationError, match="W_COMP brief validation failed"):
        await mock_ie.accept_competitive_evidence_brief(
            directive=directive,
            task=task,
            brief=brief,
            validation_report=invalid_report,
        )
