"""Unit tests for T19: Omnichannel Strategy, Funnel & Budget Allocation (W_STRAT + S_ALLOC)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
import httpx

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


def _mock_chat_transport(
    content: str,
    *,
    model: str = "test-model",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1726300000,
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


# =====================================================================
# STRAT-02: W_STRAT and S_ALLOC Reasoning Targeted Verification Tests
# =====================================================================


@pytest.mark.asyncio
async def test_strat02_telemetry_forwarding_and_bounded_s_alloc_reasoning() -> None:
    """STRAT-02: W_STRAT forwards telemetry/history/controls/incrementality to S_ALLOC, which reasons without authority."""
    from app.agents.strategy_engine.subagents import StrategyAllocationAgent

    agent = StrategyAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-strat02-telemetry",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="acme",
        objective="Analyze media history and incrementality for Q2",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context: dict[str, object] = {
        "budget_ceiling": 40000.0,
        "kpi_name": "incremental_revenue",
        "media_history": {"meta": [1000, 2000], "google": [1500, 2500]},
        "performance_telemetry": {"cpa_trend": "stable"},
        "control_variables": ["seasonality", "promo_events"],
        "incrementality_evidence": {"meta_lift": 0.18, "google_lift": 0.24},
        "channel_constraints": {"meta": {"max_spend": 20000.0}},
    }

    payload = agent.build_payload(grant, context)
    assert payload["kpi_name"] == "incremental_revenue"
    assert "media_history" in payload
    assert "performance_telemetry" in payload
    assert "control_variables" in payload
    assert "incrementality_evidence" in payload
    assert "channel_constraints" in payload

    # Test S_ALLOC advisory sub-agent processes telemetry context without numerical allocation authority
    alloc_agent = StrategyAllocationAgent()
    reasoning, meta = await alloc_agent.reason(grant, context)
    assert reasoning.objective_interpretation == "Analyze media history and incrementality for Q2"
    assert "incremental_revenue" in reasoning.kpi_priorities
    assert not any("Historical media/performance inputs are absent" in r for r in reasoning.risk_flags)
    assert not any("No incrementality calibration" in r for r in reasoning.risk_flags)


@pytest.mark.asyncio
async def test_w_strat_and_s_alloc_use_distinct_purpose_scoped_reasoning() -> None:
    """W_STRAT and S_ALLOC use independent LLMs, preserve bounded context, and record distinct provenance."""
    import httpx
    from app.agents.strategy_engine.subagents import StrategyAllocationAgent
    from app.core.settings import LlmSettings
    from app.integrations.llm.client import LlmClient

    w_strat_json = json.dumps({
        "domain_interpretation": "Omnichannel roadmap for brand scaling",
        "requires_specialist_execution": True,
        "selected_tools": ["S_ALLOC"],
        "suggested_parameters": {"operation": "optimize_budget"},
        "preliminary_findings": ["Strategic fit confirmed for multi-channel acquisition"],
        "identified_risks": ["Creative fatigue on upper-funnel channels"],
        "rationale_summary": "Delegate budget modeling to S_ALLOC",
        "estimated_confidence": 0.88,
    })
    s_alloc_json = json.dumps({
        "objective_interpretation": "Interpret media planning subtask with conservative emphasis",
        "kpi_priorities": ["incremental ROAS", "marginal return"],
        "scenario_emphasis": "conservative",
        "modeling_assumptions": ["Saturating response curves require margin-first posture"],
        "risk_flags": ["Elevated CAC during market expansion"],
        "rationale_summary": "Conservative scenario selected for capital efficiency",
        "estimated_confidence": 0.82,
    })

    w_settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="w-strat-llm")
    s_settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="s-alloc-llm")

    w_client = LlmClient(w_settings, client=httpx.AsyncClient(transport=_mock_chat_transport(w_strat_json, model="w-strat-llm")))
    s_client = LlmClient(s_settings, client=httpx.AsyncClient(transport=_mock_chat_transport(s_alloc_json, model="s-alloc-llm")))

    s_subagent = StrategyAllocationAgent(llm_client=s_client)
    agent = StrategyAgent(SandboxClient(), llm_client=w_client, allocation_agent=s_subagent)

    grant = TaskGrant(
        task_id="task-strat-distinct-01",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="acme",
        objective="Drive profitable customer acquisition",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        cts_state={"budget_cap": 20000.0},
    )
    context: dict[str, object] = {
        "budget_ceiling": 20000.0,
        "claims_dossier": {"tenant_id": "acme", "claims": [{"claim_text": "Proven results", "validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "pricing"}]},
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "Comp1"},
    }

    envelope = await agent.run(grant, context)

    # 1. Verify W_STRAT provenance
    assert envelope.provenance["llm_reasoning_used"] == "true"
    assert envelope.provenance["llm_model"] == "w-strat-llm"

    # 2. Verify distinct S_ALLOC provenance
    assert envelope.provenance["s_alloc_reasoning_used"] == "true"
    assert envelope.provenance["s_alloc_llm_model"] == "s-alloc-llm"
    assert envelope.provenance["s_alloc_scenario_emphasis"] == "conservative"

    # 3. Verify S_ALLOC conclusions reached envelope findings and risks
    assert any("S_ALLOC Advisory: Scenario 'conservative'" in f for f in envelope.findings)
    assert any("Conservative scenario selected" in f for f in envelope.findings)
    assert any("Elevated CAC during market expansion" in r for r in envelope.unresolved_risks_or_assumptions)

    # 4. Verify advisory scenario preference reached strategy plan without breaking numerical bounds
    plan = agent.extract_strategy_plan(envelope)
    assert plan is not None
    assert plan.recommended_scenario == "scenario_conservative"
    assert plan.total_allocated <= 20000.0


@pytest.mark.asyncio
async def test_s_alloc_reasoning_cannot_override_budget_ceiling_or_channels() -> None:
    """S_ALLOC advisory reasoning cannot override the authoritative budget cap or expand allowed channels."""
    import httpx
    from app.agents.strategy_engine.subagents import StrategyAllocationAgent
    from app.core.settings import LlmSettings
    from app.integrations.llm.client import LlmClient

    s_alloc_json = json.dumps({
        "objective_interpretation": "Aggressive scaling objective",
        "kpi_priorities": ["reach", "volume"],
        "scenario_emphasis": "aggressive",
        "modeling_assumptions": ["Aggressive growth posture"],
        "risk_flags": [],
        "rationale_summary": "Push maximum volume",
        "estimated_confidence": 0.75,
    })

    s_settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="s-alloc-agg")
    s_client = LlmClient(s_settings, client=httpx.AsyncClient(transport=_mock_chat_transport(s_alloc_json, model="s-alloc-agg")))
    s_subagent = StrategyAllocationAgent(llm_client=s_client)
    agent = StrategyAgent(SandboxClient(), allocation_agent=s_subagent)

    # Directive/grant authorizes $10,000 and only 'meta'
    grant = TaskGrant(
        task_id="task-strat-no-override",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta"]),
        brand_id="acme",
        objective="Scale audience reach",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        cts_state={"budget_cap": 10000.0},
    )

    # Context attempts to inject excessive budget ($80,000) and unapproved channels
    context: dict[str, object] = {
        "budget": 80000.0,
        "channels": "meta,tiktok,linkedin",
        "claims_dossier": {"tenant_id": "acme", "claims": [{"claim_text": "Proven results", "validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "pricing"}]},
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "Comp1"},
    }

    envelope = await agent.run(grant, context)
    plan = agent.extract_strategy_plan(envelope)
    assert plan is not None

    # Budget ceiling strictly enforced by IE/grant, not overridden
    assert plan.budget_ceiling == 10000.0
    assert plan.total_allocated <= 10000.0

    # Channel confined strictly to tenant scope
    channels = [ca.channel for ca in plan.channel_allocations]
    assert channels == ["meta"]
    assert "tiktok" not in channels
    assert "linkedin" not in channels

    # Advisory recommendation applied
    assert plan.recommended_scenario == "scenario_aggressive"


@pytest.mark.asyncio
async def test_s_alloc_llm_error_fallback_preserves_deterministic_execution() -> None:
    """When S_ALLOC LLM fails, advisory reasoning gracefully falls back without failing strategy execution."""
    import httpx
    from app.agents.strategy_engine.subagents import StrategyAllocationAgent
    from app.core.settings import LlmSettings
    from app.integrations.llm.client import LlmClient

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content="Internal Provider Error")

    s_settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="s-alloc-err")
    s_client = LlmClient(s_settings, client=httpx.AsyncClient(transport=httpx.MockTransport(failing_handler)))
    s_subagent = StrategyAllocationAgent(llm_client=s_client)
    agent = StrategyAgent(SandboxClient(), allocation_agent=s_subagent)

    grant = TaskGrant(
        task_id="task-strat-fallback-01",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="acme",
        objective="Balanced acquisition test",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context: dict[str, object] = {
        "budget_ceiling": 15000.0,
        "claims_dossier": {"tenant_id": "acme", "claims": [{"claim_text": "Proven results", "validation_status": "SUPPORTED"}]},
        "customer_voice_analysis": {"tenant_id": "acme", "objection_profiles": [{"theme": "pricing"}]},
        "competitor_intelligence": {"tenant_id": "acme", "competitor": "Comp1"},
    }

    envelope = await agent.run(grant, context)
    assert envelope.task_id == "task-strat-fallback-01"
    assert envelope.provenance["s_alloc_reasoning_used"] == "true"
    assert envelope.provenance["s_alloc_llm_model"] == "llm_error_fallback"

    plan = agent.extract_strategy_plan(envelope)
    assert plan is not None
    assert plan.total_allocated <= 15000.0
    assert plan.recommended_scenario == "scenario_balanced"


# =====================================================================
# STRAT-03: Governed S_ALLOC Toolchain Targeted Verification Tests
# =====================================================================


def test_strat03_channel_min_max_bounds_and_contingency() -> None:
    """Channel bounds (min/max spend/share) are strictly enforced and unallocated contingency is preserved."""
    # Test 1: Max spend constraints prevent over-allocation and preserve contingency
    payload = {
        "task_id": "task-strat03-bounds",
        "budget": "20000.0",
        "budget_ceiling": "20000.0",
        "channels": "meta,google",
        "channel_constraints": json.dumps({
            "meta": {"max_spend": 4000.0},
            "google": {"max_spend": 8000.0},
        }),
    }
    res = execute_s_alloc(payload)
    alloc = json.loads(res["allocations"])
    assert alloc["meta"] <= 4000.0
    assert alloc["google"] <= 8000.0
    assert float(res["allocated_total"]) <= 12000.0

    plan = json.loads(res["strategy_plan"])
    assert plan["total_allocated"] <= 12000.0
    assert plan["unallocated_contingency"] >= 8000.0
    assert plan["budget_ceiling"] == 20000.0

    # Test 2: Min share and max share constraints
    payload2 = {
        "task_id": "task-strat03-shares",
        "budget": "10000.0",
        "budget_ceiling": "10000.0",
        "channels": "meta,google",
        "channel_constraints": json.dumps({
            "meta": {"max_share": 0.25},
            "google": {"min_share": 0.50},
        }),
    }
    res2 = execute_s_alloc(payload2)
    alloc2 = json.loads(res2["allocations"])
    assert alloc2["meta"] <= 2500.0
    assert alloc2["google"] >= 5000.0
    assert float(res2["allocated_total"]) <= 10000.0


def test_strat03_diminishing_returns_and_mroi_reallocation() -> None:
    """Allocation pivots to higher marginal ROI under saturation rather than higher historical ROAS alone."""
    payload = {
        "task_id": "task-strat03-saturation",
        "budget": "25000.0",
        "channels": "meta,google",
        "prior_roas_meta": 3.0,
        "prior_roas_google": 4.5,  # Higher historical ROAS
        "media_history": json.dumps({
            # Google is heavily saturated with low headroom
            "google": {"spend": 20000.0, "saturation_spend": 4000.0},
            # Meta has substantial unsaturated headroom
            "meta": {"spend": 1000.0, "saturation_spend": 25000.0},
        }),
    }
    res = execute_s_alloc(payload)
    alloc = json.loads(res["allocations"])

    # Meta receives higher budget than Google because Google's marginal ROI saturates rapidly
    assert alloc["meta"] > alloc["google"]

    # Response curves show strictly diminishing marginal ROI across spend intervals
    curves = json.loads(res["response_curves"])
    assert "google" in curves and "meta" in curves
    assert curves["google"][0]["mroi"] > curves["google"][-1]["mroi"]
    assert curves["meta"][0]["mroi"] > curves["meta"][-1]["mroi"]

    marginal = json.loads(res["marginal_roas"])
    assert "google" in marginal and "meta" in marginal


def test_strat03_explicit_model_diagnostics_and_non_causal_proxy() -> None:
    """S_ALLOC results are explicitly labeled non-causal planning proxy with observable diagnostics."""
    # Standard planning execution without causal MMM
    payload = {
        "task_id": "task-strat03-diag",
        "budget": "10000.0",
        "channels": "meta,google",
    }
    res = execute_s_alloc(payload)
    diag = json.loads(res["model_diagnostics"])

    assert diag["causal_mmm"] is False
    assert diag["measurement_mode"] == "deterministic_response_curve_proxy"
    assert diag["health_status"] == "REVIEW"
    assert any("not a fitted causal MMM" in r for r in diag["health_reasons"])
    assert diag["incrementality_calibrated"] is False

    # Fail diagnostic status when budget is zero
    payload_zero = {
        "task_id": "task-strat03-zero",
        "budget": "0.0",
        "channels": "meta,google",
    }
    res_zero = execute_s_alloc(payload_zero)
    diag_zero = json.loads(res_zero["model_diagnostics"])
    assert diag_zero["health_status"] == "FAIL"
    assert any("zero" in r.lower() for r in diag_zero["health_reasons"])


def test_strat03_backend_and_sandbox_parity() -> None:
    """Backend execute_s_alloc and sandbox run_s_alloc exhibit 100% functional behavioral equivalence."""
    import importlib.util
    from pathlib import Path

    sandbox_run_path = Path(__file__).resolve().parents[3] / "sandbox" / "docker" / "hardened" / "skills" / "s-alloc" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("sandbox_s_alloc_run", str(sandbox_run_path))
    assert spec is not None and spec.loader is not None
    sandbox_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox_mod)
    sandbox_run_s_alloc = getattr(sandbox_mod, "run_s_alloc")

    test_payload = {
        "task_id": "task-strat03-parity-01",
        "tenant_id": "acme_tenant",
        "brand_id": "acme_brand",
        "budget": "30000.0",
        "budget_ceiling": "25000.0",
        "channels": "meta,google,tiktok",
        "prior_roas_meta": "3.5",
        "prior_roas_google": "4.2",
        "prior_roas_tiktok": "2.8",
        "channel_constraints": json.dumps({
            "meta": {"max_spend": 10000.0},
            "google": {"min_spend": 5000.0, "max_spend": 15000.0},
        }),
        "media_history": json.dumps({
            "meta": {"spend": 5000.0, "saturation_spend": 12000.0},
            "google": {"spend": 10000.0, "saturation_spend": 8000.0},
        }),
        "incrementality_evidence": json.dumps({
            "meta": {"lift_multiplier": 1.15},
        }),
        "t16_claims": json.dumps([{"text": "Clinically validated", "status": "SUPPORTED"}]),
        "t17_objections": json.dumps([{"theme": "price_point"}]),
        "t18_competitor": json.dumps({"competitor": "Rival", "threat_level": "high"}),
    }

    backend_res = execute_s_alloc(test_payload)
    sandbox_res = sandbox_run_s_alloc(test_payload)

    # Assert exact functional equivalence across all outputs
    assert backend_res["status"] == sandbox_res["status"] == "success"
    assert backend_res["budget_total"] == sandbox_res["budget_total"]
    assert backend_res["allocated_total"] == sandbox_res["allocated_total"]
    assert json.loads(backend_res["allocations"]) == json.loads(sandbox_res["allocations"])
    assert backend_res["expected_blended_roas"] == sandbox_res["expected_blended_roas"]
    assert backend_res["primary_channel"] == sandbox_res["primary_channel"]
    assert json.loads(backend_res["marginal_roas"]) == json.loads(sandbox_res["marginal_roas"])
    assert json.loads(backend_res["response_curves"]) == json.loads(sandbox_res["response_curves"])
    assert json.loads(backend_res["model_diagnostics"]) == json.loads(sandbox_res["model_diagnostics"])
    assert json.loads(backend_res["funnel_model"]) == json.loads(sandbox_res["funnel_model"])
    assert json.loads(backend_res["scenarios"]) == json.loads(sandbox_res["scenarios"])
    assert json.loads(backend_res["strategy_plan"]) == json.loads(sandbox_res["strategy_plan"])


def test_strat03_backward_compatible_existing_outputs_and_schema_extraction() -> None:
    """Enhanced S_ALLOC payload extracts into typed OmnichannelStrategyPlan and preserves legacy keys."""
    payload = {
        "task_id": "task-strat03-compat",
        "budget": "15000.0",
        "budget_ceiling": "15000.0",
        "channels": "meta,google,tiktok",
    }
    result = execute_s_alloc(payload)

    # Legacy public keys preserved
    assert "status" in result
    assert "task_id" in result
    assert "budget_total" in result
    assert "allocated_total" in result
    assert "allocations" in result
    assert "expected_blended_roas" in result
    assert "primary_channel" in result
    assert "funnel_model" in result
    assert "scenarios" in result
    assert "strategy_plan" in result

    # New STRAT-03 keys present
    assert "marginal_roas" in result
    assert "response_curves" in result
    assert "model_diagnostics" in result

    # Fully validates into typed OmnichannelStrategyPlan schema
    plan = OmnichannelStrategyPlan.model_validate_json(result["strategy_plan"])
    assert plan.plan_id == "strat-task-strat03-compat"
    assert plan.budget_ceiling == 15000.0
    assert plan.total_allocated <= 15000.0
    assert plan.unallocated_contingency >= 0.0
    assert len(plan.channel_allocations) == 3
    assert len(plan.funnel_stages) == 4
    assert len(plan.scenarios) == 3
    assert plan.provenance["modeled_by"] == "S_ALLOC"
    assert plan.provenance["model_diagnostics"]["causal_mmm"] is False


# =====================================================================
# STRAT-04: Enforce AIO-Sandbox Execution Boundary Targeted Tests
# =====================================================================


@pytest.mark.asyncio
async def test_strat04_configured_s_alloc_uses_remote_sandbox_apis_and_scoped_workspace() -> None:
    """When SANDBOX_ENDPOINT is configured, S_ALLOC executes via remote file and shell APIs in an execution-scoped workspace."""
    from unittest.mock import MagicMock
    from app.core.settings import SandboxSettings
    from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxExecutionStatus, SandboxInvocationMandate

    mock_remote = MagicMock()
    mock_remote.file.write_file.return_value = None
    mock_remote.shell.exec_command.return_value = MagicMock(exit_code=0, stderr="")
    mock_remote.file.read_file.return_value = MagicMock(
        data=MagicMock(content=json.dumps({
            "status": "success",
            "task_id": "task-strat04-remote",
            "budget_total": "10000.0",
            "allocated_total": "10000.0",
            "allocations": json.dumps({"meta": 5000.0, "google": 5000.0}),
            "expected_blended_roas": "3.5",
            "primary_channel": "meta",
            "strategy_plan": json.dumps({
                "plan_id": "strat-task-strat04-remote",
                "tenant_id": "tenant_01",
                "brand_id": "brand_01",
                "time_horizon": "90_days",
                "budget_ceiling": 10000.0,
                "total_allocated": 10000.0,
            }),
        }))
    )

    settings = SandboxSettings(endpoint="http://remote-sandbox:8080")
    client = SandboxClient(settings=settings)
    client._sandbox = mock_remote

    mandate = SandboxInvocationMandate(
        task_id="task-strat04-remote",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0", "channels": "meta,google"},
        network_policy=NetworkPolicy.DISABLED,
    )

    result = await client.invoke(mandate)

    assert result.success is True
    assert result.status == SandboxExecutionStatus.COMPLETED

    exec_id = mandate.execution_id
    scoped_dir = f"/workspace/{exec_id}"
    input_file = f"{scoped_dir}/input.json"
    output_file = f"{scoped_dir}/output.json"

    # Verify execution-scoped directory creation
    mock_remote.shell.exec_command.assert_any_call(command=f"mkdir -p {scoped_dir}")

    # Verify payload written to scoped input file
    mock_remote.file.write_file.assert_called_once_with(
        file=input_file,
        content=json.dumps(mandate.payload, ensure_ascii=False),
    )

    # Verify programmatic invocation of mounted skill script with redirection
    expected_cmd = f"python /home/gem/skills/s-alloc/scripts/run.py < {input_file} > {output_file}"
    mock_remote.shell.exec_command.assert_any_call(command=expected_cmd)

    # Verify reading from output file
    mock_remote.file.read_file.assert_called_once_with(file=output_file)


@pytest.mark.asyncio
async def test_strat04_configured_remote_failure_fails_closed_without_local_fallback() -> None:
    """Configured remote sandbox failure fails closed with FAILED status and never falls back to local micro-tools."""
    from unittest.mock import MagicMock, patch
    from app.core.settings import SandboxSettings
    from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxExecutionStatus, SandboxInvocationMandate

    mock_remote = MagicMock()
    mock_remote.shell.exec_command.return_value = MagicMock(exit_code=1, stderr="Remote process crashed")

    settings = SandboxSettings(endpoint="http://remote-sandbox:8080")
    client = SandboxClient(settings=settings)
    client._sandbox = mock_remote

    mandate = SandboxInvocationMandate(
        task_id="task-strat04-fail",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0", "channels": "meta,google"},
        network_policy=NetworkPolicy.DISABLED,
    )

    with patch("app.integrations.sandbox.client.dispatch_micro_tool") as mock_dispatch:
        result = await client.invoke(mandate)

        # Fails closed
        assert result.success is False
        assert result.status == SandboxExecutionStatus.FAILED
        assert "exit code 1" in str(result.error)

        # Proves local fallback was NEVER invoked
        mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_strat04_endpoint_configured_but_unreachable_fails_closed() -> None:
    """When SANDBOX_ENDPOINT is configured but initialization/execution fails, it fails closed without silent fallback."""
    from unittest.mock import patch
    from app.core.settings import SandboxSettings
    from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxExecutionStatus, SandboxInvocationMandate

    settings = SandboxSettings(endpoint="http://unreachable-sandbox:8080")
    client = SandboxClient(settings=settings)

    mandate = SandboxInvocationMandate(
        task_id="task-strat04-init-fail",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0", "channels": "meta,google"},
        network_policy=NetworkPolicy.DISABLED,
    )

    with patch("app.integrations.sandbox.client.dispatch_micro_tool") as mock_dispatch:
        result = await client.invoke(mandate)

        assert result.success is False
        assert result.status == SandboxExecutionStatus.FAILED
        assert result.error is not None and len(result.error) > 0
        mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_strat04_no_endpoint_retains_local_fallback() -> None:
    """When no sandbox endpoint is configured, execution safely uses local micro-tool fallback."""
    from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxExecutionStatus, SandboxInvocationMandate

    client = SandboxClient(settings=None)

    mandate = SandboxInvocationMandate(
        task_id="task-strat04-no-endpoint",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0", "channels": "meta,google"},
        network_policy=NetworkPolicy.DISABLED,
    )

    result = await client.invoke(mandate)
    assert result.success is True
    assert result.status == SandboxExecutionStatus.COMPLETED
    assert "allocations" in result.sanitized_output


@pytest.mark.asyncio
async def test_strat04_network_disabled_and_external_url_rejected_for_s_alloc() -> None:
    """S_ALLOC has network_policy DISABLED; any attempt to pass external URLs fails closed immediately."""
    from app.core.exceptions import SandboxInvocationError
    from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate

    client = SandboxClient(settings=None)

    mandate = SandboxInvocationMandate(
        task_id="task-strat04-net-reject",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0", "channels": "meta,google", "url": "https://malicious-external-target.com"},
        network_policy=NetworkPolicy.DISABLED,
    )

    with pytest.raises(SandboxInvocationError, match="Network access denied"):
        await client.invoke(mandate)


def test_strat04_docker_compose_hardened_spec_enforces_isolation() -> None:
    """Hardened docker-compose guarantees tmpfs workspace, ro skills mount, DENY_ALL egress, and no backend source mount."""
    from pathlib import Path
    compose_path = Path(__file__).resolve().parents[3] / "sandbox" / "docker" / "hardened" / "docker-compose.hardened.yaml"
    assert compose_path.exists()
    content = compose_path.read_text(encoding="utf-8")

    # Verify ro skills mount
    assert "./skills:/home/gem/skills:ro" in content
    # Verify tmpfs workspace
    assert "/workspace:rw,size=2048m" in content
    # Verify default DENY_ALL network policy
    assert "EGRESS_NETWORK_POLICY: DENY_ALL" in content
    # Verify no backend or repo source mounted
    assert "backend:" not in content
    assert "../backend" not in content
    assert "../../backend" not in content


# =====================================================================
# STRAT-05: Holistic Omnichannel Strategy Synthesis Verification Tests
# =====================================================================


@pytest.mark.asyncio
async def test_strat05_w_strat_holistic_strategy_synthesis_and_boundary_integrity() -> None:
    """STRAT-05: W_STRAT owns holistic strategy synthesis; S_ALLOC provides bounded quantitative modeling."""
    agent = StrategyAgent(SandboxClient())

    grant = TaskGrant(
        task_id="task-strat05-holistic",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme_corp", allowed_channels=["meta", "google"]),
        brand_id="acme_brand",
        objective="Assemble holistic omnichannel acquisition strategy for Q1",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "budget_ceiling": 30000.0,
        "claims_dossier": {
            "tenant_id": "acme_corp",
            "claims": [
                {
                    "claim_id": "claim-c1",
                    "claim_text": "Clinically proven 3x skin barrier repair in 14 days",
                    "validation_status": "SUPPORTED",
                    "confidence": 0.95,
                }
            ],
        },
        "customer_voice_analysis": {
            "tenant_id": "acme_corp",
            "objection_profiles": [
                {"theme": "subscription_lock_in_concern", "frequency": 8}
            ],
        },
        "competitor_intelligence": {
            "tenant_id": "acme_corp",
            "competitor": "RivalBeauty",
            "threat_level": "high",
            "benchmark_price": "49.00",
        },
    }

    envelope = await agent.run(grant, context)

    # 1. W_STRAT Envelope structure & artifacts
    assert envelope.task_id == "task-strat05-holistic"
    assert envelope.worker_role == WorkerRole.STRATEGY
    assert f"strategy:{grant.task_id}" in envelope.generated_artifacts

    # 2. Plan extraction & synthesis ownership
    plan = agent.extract_strategy_plan(envelope)
    assert plan is not None
    assert plan.plan_id == f"strat-{grant.task_id}"
    assert plan.provenance["synthesized_by"] == "W_STRAT"
    assert plan.provenance["modeled_by"] == "S_ALLOC"

    # 3. Budget ceiling and channel scope strictly bounded
    assert plan.budget_ceiling == 30000.0
    assert plan.total_allocated <= 30000.0
    assert plan.unallocated_contingency >= 0.0
    assert len(plan.channel_allocations) == 2
    assert {ca.channel for ca in plan.channel_allocations} == {"meta", "google"}
    # Roles strategically synthesized by W_STRAT
    for ca in plan.channel_allocations:
        assert len(ca.role) > 0

    # 4. Verified IE evidence grounded into plan
    assert any("Clinically proven" in c for c in plan.approved_claims_applied)
    assert any("subscription_lock_in_concern" in o for o in plan.objections_addressed)
    assert any("RivalBeauty" in comp for comp in plan.competitor_signals_factored)

    # 5. Non-causal caveats and model limitations explicitly documented
    assert any("deterministic response-curve planning proxy" in c.lower() for c in plan.unsupported_estimates_or_caveats)
    assert any("not a fitted causal mmm" in c.lower() for c in plan.unsupported_estimates_or_caveats)
    assert any("historical media/performance inputs are absent" in c.lower() for c in plan.unsupported_estimates_or_caveats)



