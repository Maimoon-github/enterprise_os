"""Unit tests for T19: Omnichannel Strategy, Funnel & Budget Allocation (W_STRAT + S_ALLOC)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.strategy import StrategyAgent
from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.micro_tools import execute_s_alloc
from app.schemas.agent_contracts import (
    ChannelAllocation,
    ConfidenceInterval,
    EvidenceEnvelope,
    FunnelStageAllocation,
    OmnichannelStrategyPlan,
    StrategyScenario,
    TaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from tests.conftest import FakeSandboxClient


def test_s_alloc_valid_inputs_and_evidence_influence() -> None:
    """S_ALLOC models channel allocation, 4-tier funnel, and multi-scenario comparison with T16-T18 evidence."""
    payload = {
        "task_id": "task-strat-001",
        "tenant_id": "acme_wellness",
        "brand_id": "acme_glow",
        "budget": "50000.0",
        "budget_ceiling": "50000.0",
        "channels": "meta,google,tiktok,linkedin,email",
        "t16_claims": json.dumps([
            {"id": "claim-1", "text": "Clinically proven 42% hydration improvement in 28 days.", "status": "SUPPORTED"}
        ]),
        "t17_objections": json.dumps([
            {"theme": "price_perceived_high", "frequency": 12},
            {"theme": "shipping_latency", "frequency": 4},
        ]),
        "t18_competitor": json.dumps({
            "competitor": "LuxeCompetitor",
            "benchmark_price": "59.99",
            "active_ads": 24,
            "threat_level": "high",
            "pricing_trajectory": "discounting_aggressive",
        }),
    }

    result = execute_s_alloc(payload)

    assert result["status"] == "success"
    assert result["task_id"] == "task-strat-001"
    assert float(result["budget_total"]) == 50000.0
    assert float(result["allocated_total"]) <= 50000.0

    allocs = json.loads(result["allocations"])
    assert "google" in allocs
    assert "meta" in allocs
    # Google Search is boosted due to high competitor threat & objection neutralization
    assert allocs["google"] > 0
    assert allocs["meta"] > 0
    assert round(sum(allocs.values()), 2) <= 50000.0

    # Verify Funnel Model
    funnel = json.loads(result["funnel_model"])
    assert len(funnel) == 4
    stages = [f["stage"] for f in funnel]
    assert stages == ["TOFU", "MOFU", "BOFU", "RETENTION"]
    funnel_sum = round(sum(f["allocated_amount"] for f in funnel), 2)
    assert funnel_sum <= 50000.0

    # Verify Scenarios
    scenarios = json.loads(result["scenarios"])
    assert len(scenarios) == 3
    sc_ids = [s["scenario_id"] for s in scenarios]
    assert "scenario_balanced" in sc_ids
    assert "scenario_aggressive" in sc_ids
    assert "scenario_conservative" in sc_ids

    rec = next(s for s in scenarios if s["is_recommended"])
    assert rec["scenario_id"] == "scenario_balanced"

    # Verify Full Omnichannel Strategy Plan JSON
    plan = OmnichannelStrategyPlan.model_validate_json(result["strategy_plan"])
    assert plan.plan_id == "strat-task-strat-001"
    assert plan.budget_ceiling == 50000.0
    assert plan.total_allocated <= 50000.0
    assert len(plan.approved_claims_applied) >= 1
    assert len(plan.objections_addressed) >= 1
    assert len(plan.competitor_signals_factored) >= 1
    assert len(plan.assumptions) >= 1
    assert len(plan.unsupported_estimates_or_caveats) >= 1


@pytest.mark.asyncio
async def test_w_strat_generates_valid_evidence_envelope_and_strategy_plan() -> None:
    """StrategyAgent processes full T16-T18 inputs and produces valid EvidenceEnvelope with strategy artifact."""
    sandbox_client = SandboxClient()
    agent = StrategyAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-strat-plan-1",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google", "tiktok"]),
        brand_id="acme",
        objective="Formulate Q4 omnichannel acquisition strategy",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "budget_ceiling": 25000.0,
        "claims_dossier": {
            "tenant_id": "acme",
            "claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "Clinically proven to reduce wrinkles by 35%",
                    "validation_status": "SUPPORTED",
                    "confidence": 0.92,
                }
            ],
        },
        "customer_voice_analysis": {
            "tenant_id": "acme",
            "objection_profiles": [
                {"objection_type": "price_point", "theme": "Too expensive without trial", "frequency": 15}
            ],
        },
        "competitor_intelligence": {
            "tenant_id": "acme",
            "competitor": "SkinCo",
            "benchmark_price": "45.00",
            "active_ads": 18,
            "threat_level": "medium",
        },
    }

    envelope = await agent.run(grant, context)

    assert envelope.task_id == "task-strat-plan-1"
    assert envelope.worker_role == WorkerRole.STRATEGY
    assert envelope.confidence.point_estimate >= 0.75
    assert "strategy:task-strat-plan-1" in envelope.generated_artifacts
    assert envelope.provenance["capability"] == "S_ALLOC"
    assert len(envelope.findings) >= 3

    # Typed model extraction
    plan = agent.extract_strategy_plan(envelope)
    assert plan is not None
    assert plan.total_allocated <= 25000.0
    assert plan.budget_ceiling == 25000.0
    assert len(plan.channel_allocations) == 3
    assert plan.recommended_scenario == "scenario_balanced"


@pytest.mark.asyncio
async def test_missing_t16_product_evidence_fails_closed() -> None:
    """StrategyAgent fails closed with ValueError when T16 verified claims evidence is missing."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-strat-fail-t16",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "budget_ceiling": 10000.0,
        # T16 missing!
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "slow"}]},
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "CompA"},
    }

    with pytest.raises(ValueError, match="Missing or invalid T16 dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_missing_t17_customer_voice_fails_closed() -> None:
    """StrategyAgent fails closed with ValueError when T17 customer voice/objections evidence is missing."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-strat-fail-t17",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "budget_ceiling": 10000.0,
        "claims_dossier": {"tenant_id": "acme", "claims": [{"validation_status": "SUPPORTED"}]},
        # T17 missing!
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "CompA"},
    }

    with pytest.raises(ValueError, match="Missing or invalid T17 dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_missing_t18_competitor_intel_fails_closed() -> None:
    """StrategyAgent fails closed with ValueError when T18 competitor intelligence evidence is missing."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-strat-fail-t18",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "budget_ceiling": 10000.0,
        "claims_dossier": {"tenant_id": "acme", "claims": [{"validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "slow"}]},
        # T18 missing!
    }

    with pytest.raises(ValueError, match="Missing or invalid T18 dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_budget_overflow_strictly_capped_at_ceiling() -> None:
    """Allocated total must never exceed authorized budget ceiling even if requested budget is excessive."""
    payload = {
        "task_id": "task-strat-overflow",
        "tenant_id": "acme",
        "budget": "100000.0",
        "budget_ceiling": "20000.0",  # Ceiling lower than requested budget
        "channels": "meta,google,tiktok",
    }

    result = execute_s_alloc(payload)
    assert float(result["budget_total"]) == 20000.0
    assert float(result["allocated_total"]) <= 20000.0
    allocs = json.loads(result["allocations"])
    assert round(sum(allocs.values()), 2) <= 20000.0


def test_invalid_and_empty_allocation_channels_handled_safely() -> None:
    """Malformed or empty channel lists gracefully fall back to defaults without unhandled exception."""
    res1 = execute_s_alloc({"budget": "-500", "channels": ""})
    assert float(res1["budget_total"]) == 0.0

    res2 = execute_s_alloc({"budget": "abc", "channels": "  ,  ,,  "})
    assert float(res2["budget_total"]) == 10000.0
    allocs = json.loads(res2["allocations"])
    assert len(allocs) >= 1


@pytest.mark.asyncio
async def test_cross_tenant_evidence_rejected_fail_closed() -> None:
    """T16, T17, or T18 evidence tagged with a foreign tenant_id triggers fail-closed tenant isolation breach."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-strat-isolation",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme_legit"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    # T16 has off-tenant evidence
    context_bad_t16: dict[str, object] = {
        "claims_dossier": {"tenant_id": "hostile_attacker", "claims": [{"validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme_legit", "objection_profiles": [{"theme": "none"}]},
        "competitor_intelligence": {"tenant_id": "acme_legit", "competitor": "CompA"},
    }
    with pytest.raises(ValueError, match="Tenant isolation breach in T16"):
        await agent.run(grant, context_bad_t16)

    # T17 has off-tenant evidence
    context_bad_t17: dict[str, object] = {
        "claims_dossier": {"tenant_id": "acme_legit", "claims": [{"validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "hostile_attacker", "objection_profiles": [{"theme": "none"}]},
        "competitor_intelligence": {"tenant_id": "acme_legit", "competitor": "CompA"},
    }
    with pytest.raises(ValueError, match="Tenant isolation breach in T17"):
        await agent.run(grant, context_bad_t17)

    # T18 has off-tenant evidence
    context_bad_t18: dict[str, object] = {
        "claims_dossier": {"tenant_id": "acme_legit", "claims": [{"validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme_legit", "objection_profiles": [{"theme": "none"}]},
        "competitor_intelligence": {"tenant_id": "hostile_attacker", "competitor": "CompA"},
    }
    with pytest.raises(ValueError, match="Tenant isolation breach in T18"):
        await agent.run(grant, context_bad_t18)


def test_unauthorized_capability_rejected_for_w_strat() -> None:
    """W_STRAT is strictly authorized ONLY for SandboxCapability.ALLOC; all other 6 capabilities are denied."""
    profile = validate_capability_access(
        capability=SandboxCapability.ALLOC,
        worker_role=WorkerRole.STRATEGY,
        operation="optimize_budget",
    )
    assert profile.allowed_worker == WorkerRole.STRATEGY

    denied_capabilities = [
        SandboxCapability.CODE,
        SandboxCapability.COPY,
        SandboxCapability.VAL,
        SandboxCapability.SCRAPE,
        SandboxCapability.PARSE,
        SandboxCapability.ATTR,
    ]

    for cap in denied_capabilities:
        with pytest.raises(SandboxInvocationError, match="Capability access denied"):
            validate_capability_access(
                capability=cap,
                worker_role=WorkerRole.STRATEGY,
                operation="any_op",
            )


def test_unsupported_forecasts_and_caveats_explicitly_flagged() -> None:
    """Strategy output separates observed inputs vs mathematical projections and includes explicit model caveats."""
    payload = {
        "task_id": "task-strat-caveat",
        "budget": "30000.0",
        "channels": "meta,google",
        "t16_claims": json.dumps([{"text": "Supported claim", "status": "SUPPORTED"}]),
        "t17_objections": json.dumps([{"theme": "objection1"}]),
        "t18_competitor": json.dumps({"competitor": "CompX"}),
    }
    result = execute_s_alloc(payload)
    plan = OmnichannelStrategyPlan.model_validate_json(result["strategy_plan"])

    assert len(plan.unsupported_estimates_or_caveats) >= 1
    assert any("not guaranteed financial results" in c.lower() or "mathematical" in c.lower() for c in plan.unsupported_estimates_or_caveats)
    assert len(plan.assumptions) >= 1


@pytest.mark.asyncio
async def test_s_alloc_failure_handled_safely() -> None:
    """When sandbox invocation fails (e.g. timeout or execution error), agent returns zero-confidence envelope safely."""
    fake_client = FakeSandboxClient(should_fail=True)
    agent = StrategyAgent(fake_client)  # type: ignore[arg-type]

    grant = TaskGrant(
        task_id="task-strat-err",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context: dict[str, object] = {
        "claims_dossier": {"tenant_id": "acme", "claims": [{"validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "price"}]},
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "Comp"},
    }

    envelope = await agent.run(grant, context)

    assert envelope.task_id == "task-strat-err"
    assert envelope.confidence.point_estimate == 0.0
    assert any("sandbox execution failed" in e.lower() for e in envelope.evidence)
    assert len(envelope.unresolved_risks_or_assumptions) >= 1
    assert envelope.proposed_state_changes["status"] == "failed"


def test_scenario_comparison_modeling() -> None:
    """S_ALLOC models 3 distinct scenarios (Balanced, Aggressive Scale, Conservative ROAS) with varying risk profiles."""
    payload = {
        "task_id": "task-strat-scenarios",
        "budget": "60000.0",
        "channels": "meta,google,tiktok",
    }
    result = execute_s_alloc(payload)
    scenarios = json.loads(result["scenarios"])

    balanced = next(s for s in scenarios if s["scenario_id"] == "scenario_balanced")
    aggressive = next(s for s in scenarios if s["scenario_id"] == "scenario_aggressive")
    conservative = next(s for s in scenarios if s["scenario_id"] == "scenario_conservative")

    assert balanced["is_recommended"] is True
    assert aggressive["is_recommended"] is False
    assert conservative["is_recommended"] is False

    assert aggressive["risk_level"] == "high"
    assert conservative["risk_level"] == "low"
    assert balanced["risk_level"] == "medium"

    # Aggressive has higher TOFU allocation than Conservative
    assert aggressive["allocations_by_stage"]["TOFU"] > conservative["allocations_by_stage"]["TOFU"]
    # Conservative has higher BOFU allocation than Aggressive
    assert conservative["allocations_by_stage"]["BOFU"] > aggressive["allocations_by_stage"]["BOFU"]


def test_s_alloc_subagent_has_no_reverse_w_strat_or_disallowed_imports() -> None:
    """S_ALLOC must not import W_STRAT, IE internals, RAG, persistence, databases, or outbound gateways."""
    import ast
    from pathlib import Path

    subagent_file = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "agents"
        / "strategy_engine"
        / "subagents"
        / "allocation.py"
    )
    assert subagent_file.exists(), f"Subagent file not found: {subagent_file}"

    tree = ast.parse(subagent_file.read_text(encoding="utf-8"))
    disallowed_prefixes = (
        "app.agents.strategy_engine.strategy",
        "app.agents.strategy",
        "app.orchestration.intelligence_engine",
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.integrations.ads",
        "app.integrations.social",
        "app.integrations.cms",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in disallowed_prefixes:
                    assert not alias.name.startswith(prefix), (
                        f"Disallowed import in S_ALLOC: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), (
                    f"Disallowed import in S_ALLOC: {node.module}"
                )
            if "strategy" in node.module:
                assert "StrategyAgent" not in [a.name for a in node.names], (
                    "Reverse dependency: S_ALLOC must not import StrategyAgent"
                )


def test_w_strat_preserves_tenant_channel_boundary_and_caps_budget() -> None:
    """Context channels cannot expand tenant scope allowed channels, and budget is clamped to grant cap."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-channel-scope-1",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="acme",
        objective="Channel isolation test",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        cts_state={"budget_cap": 15000.0},
    )

    # Context attempts to expand channels to include tiktok and linkedin, and exceed budget
    context: dict[str, object] = {
        "channels": "meta,google,tiktok,linkedin",
        "budget": 50000.0,
    }

    payload = agent.build_payload(grant, context)
    allowed_ch = payload["allowed_channels"].split(",")
    assert allowed_ch == ["meta", "google"], f"Channel scope was improperly expanded: {allowed_ch}"
    assert float(payload["budget"]) == 15000.0
    assert float(payload["budget_ceiling"]) == 15000.0


def test_no_fabricated_evidence_when_dependencies_absent_in_w_strat() -> None:
    """When dependencies are absent and not explicitly required, W_STRAT passes empty lists without fabrication."""
    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-no-fabrication",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta"]),
        brand_id="acme",
        objective="No fabrication test",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    payload = agent.build_payload(grant, context={})
    assert json.loads(payload["t16_claims"]) == []
    assert json.loads(payload["t17_objections"]) == []
    assert json.loads(payload["t18_competitor"]) == {}


def test_s_alloc_capability_spec_enforces_disabled_network() -> None:
    """ALLOC capability registry profile enforces disabled network, correct worker role, and canonical tools."""
    from app.integrations.sandbox.capabilities import CAPABILITY_REGISTRY
    from app.schemas.sandbox import NetworkPolicy

    profile = CAPABILITY_REGISTRY[SandboxCapability.ALLOC]
    assert profile.network_policy == NetworkPolicy.DISABLED
    assert profile.allowed_worker == WorkerRole.STRATEGY
    assert "model_media_mix" in profile.allowed_operations
    assert "simulate_funnel" in profile.allowed_operations
    assert "media_mix_modeler" in profile.allowed_tools
    assert "budget_allocator_tool" in profile.allowed_tools
    assert "funnel_simulator" in profile.allowed_tools
    assert "optimization_modeler" in profile.allowed_tools

