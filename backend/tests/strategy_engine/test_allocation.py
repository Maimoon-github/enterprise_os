"""Tests for deterministic Strategy allocation mathematics (S_ALLOC & advisory subagent).

Covers zero/exact budgets, authorized ceilings, channel min/max constraints,
impossible/edge constraints, allocation sums, duplicate/empty channels,
deterministic repeatability, and representative diminishing-return behavior.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.strategy_engine.subagents import (
    AllocationReasoningOutput,
    StrategyAllocationAgent,
)
from app.integrations.sandbox.s_alloc_core import execute_s_alloc
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole


# =============================================================================
# 1. Deterministic Repeatability & Diminishing Returns
# =============================================================================


def test_allocation_deterministic_repeatability() -> None:
    """Repeated execution with identical inputs produces bit-for-bit identical outputs."""
    payload = {
        "task_id": "task-alloc-det",
        "tenant_id": "tenant-glow",
        "budget": "30000.0",
        "channels": "meta,google,tiktok",
        "t16_claims": json.dumps([{"text": "Clinically proven hydration", "status": "SUPPORTED"}]),
        "t17_objections": json.dumps([{"theme": "price", "frequency": 5}]),
        "t18_competitor": json.dumps({"competitor": "SerumCo", "threat_level": "medium"}),
    }

    run_1 = execute_s_alloc(payload)
    run_2 = execute_s_alloc(payload)

    assert run_1["status"] == "success"
    assert run_1["allocations"] == run_2["allocations"]
    assert run_1["expected_blended_roas"] == run_2["expected_blended_roas"]
    assert run_1["strategy_plan"] == run_2["strategy_plan"]


def test_allocation_diminishing_returns_and_priors() -> None:
    """Channels with higher prior ROAS receive priority allocation before diminishing returns."""
    base_payload = {
        "task_id": "task-alloc-roas",
        "tenant_id": "tenant-glow",
        "budget": "20000.0",
        "channels": "meta,google",
        "prior_roas_meta": "4.5",
        "prior_roas_google": "2.0",
    }
    result = execute_s_alloc(base_payload)
    assert result["status"] == "success"
    allocations = json.loads(result["allocations"])
    assert float(allocations["meta"]) > float(allocations["google"])


# =============================================================================
# 2. Budget Bounds, Zero Budget & Exact Ceilings
# =============================================================================


def test_allocation_zero_budget() -> None:
    """Zero budget allocates 0.0 spend across all channels without division by zero."""
    payload = {
        "task_id": "task-alloc-zero",
        "tenant_id": "tenant-glow",
        "budget": "0.0",
        "channels": "meta,google",
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    assert float(result["budget_total"]) == 0.0
    allocations = json.loads(result["allocations"])
    for ch_spend in allocations.values():
        assert float(ch_spend) == 0.0


def test_allocation_exact_ceiling_sum_consistency() -> None:
    """Sum of channel allocations plus any contingency equals or does not exceed budget ceiling."""
    budget = 45000.0
    payload = {
        "task_id": "task-alloc-exact",
        "tenant_id": "tenant-glow",
        "budget": str(budget),
        "channels": "meta,google,tiktok,linkedin",
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    allocations = json.loads(result["allocations"])
    total_allocated = sum(float(item) for item in allocations.values())
    assert total_allocated <= budget + 0.01


# =============================================================================
# 3. Channel Constraints & Edge Cases
# =============================================================================


def test_allocation_channel_min_max_constraints() -> None:
    """Channel constraints enforce minimum and maximum spend floors and ceilings."""
    payload = {
        "task_id": "task-alloc-constraints",
        "tenant_id": "tenant-glow",
        "budget": "30000.0",
        "channels": "meta,google",
        "channel_constraints": json.dumps({
            "meta": {"min_spend": 10000.0, "max_spend": 12000.0},
            "google": {"min_spend": 5000.0},
        }),
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    allocations = json.loads(result["allocations"])
    assert float(allocations["meta"]) >= 10000.0 - 0.01
    assert float(allocations["meta"]) <= 12000.0 + 0.01
    assert float(allocations["google"]) >= 5000.0 - 0.01


def test_allocation_duplicate_and_empty_channels() -> None:
    """Duplicate or whitespace-padded channels are deduplicated cleanly."""
    payload = {
        "task_id": "task-alloc-dedup",
        "tenant_id": "tenant-glow",
        "budget": "15000.0",
        "channels": "meta, google, META, , google ",
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    allocations = json.loads(result["allocations"])
    assert set(allocations.keys()) == {"meta", "google"}


def test_allocation_impossible_constraints_fail_closed() -> None:
    """Impossible constraints (e.g. min spend exceeding total budget) fail closed with INFEASIBLE status."""
    payload = {
        "task_id": "task-alloc-impossible",
        "tenant_id": "tenant-glow",
        "budget": "10000.0",
        "channels": "meta,google",
        "channel_constraints": json.dumps({
            "meta": {"min_spend": 15000.0},  # Exceeds total budget of 10000
        }),
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "error"
    assert result["domain_status"] == "INFEASIBLE"


def test_allocation_synthetic_probe_1_empty_input() -> None:
    """Probe 1: Empty input returns INVALID_INPUT without fabricating defaults."""
    result = execute_s_alloc({})
    assert result["status"] == "error"
    assert result["domain_status"] == "INVALID_INPUT"
    diag = json.loads(result["model_diagnostics"])
    assert diag["health_status"] == "FAIL"


def test_allocation_synthetic_probe_2_sum_minima_exceeds_budget() -> None:
    """Probe 2: Budget 100, two channel minima of 80 each (80 + 80 = 160 > 100) -> INFEASIBLE."""
    payload = {
        "task_id": "probe-2",
        "budget": 100.0,
        "channels": ["meta", "google"],
        "channel_constraints": {
            "meta": {"min_spend": 80.0},
            "google": {"min_spend": 80.0},
        },
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "error"
    assert result["domain_status"] == "INFEASIBLE"


def test_allocation_synthetic_probe_3_min_exceeds_max() -> None:
    """Probe 3: Budget 100, channel minimum 80, maximum 20 (L > U) -> INFEASIBLE."""
    payload = {
        "task_id": "probe-3",
        "budget": 100.0,
        "channels": ["meta", "google"],
        "channel_constraints": {
            "meta": {"min_spend": 80.0, "max_spend": 20.0},
        },
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "error"
    assert result["domain_status"] == "INFEASIBLE"


def test_allocation_synthetic_probe_4_all_scenarios_respect_caps() -> None:
    """Probe 4: Budget 100, caps meta=20, google=80 -> Every scenario respects 20/80 caps without normalization violation."""
    payload = {
        "task_id": "probe-4",
        "budget": 100.0,
        "channels": ["meta", "google"],
        "channel_constraints": {
            "meta": {"max_spend": 20.0},
            "google": {"max_spend": 80.0},
        },
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    scenarios = json.loads(result["scenarios"])
    for sc in scenarios:
        allocs = sc["allocations_by_channel"]
        assert allocs["meta"] <= 20.0001, f"Scenario {sc['scenario_id']} violated meta cap"
        assert allocs["google"] <= 80.0001, f"Scenario {sc['scenario_id']} violated google cap"
        assert sum(allocs.values()) <= 100.0001, f"Scenario {sc['scenario_id']} exceeded budget"


def test_allocation_synthetic_probe_5_explicit_zero_budget() -> None:
    """Probe 5: Explicit zero budget returns zero spend with FAIL health status."""
    payload = {
        "task_id": "probe-5",
        "budget": 0.0,
        "channels": ["meta", "google"],
    }
    result = execute_s_alloc(payload)
    assert result["status"] == "success"
    assert float(result["budget_total"]) == 0.0
    assert float(result["allocated_total"]) == 0.0
    allocs = json.loads(result["allocations"])
    assert allocs == {"meta": 0.0, "google": 0.0}
    diag = json.loads(result["model_diagnostics"])
    assert diag["health_status"] == "FAIL"


def test_allocation_exact_currency_quantization_and_stable_tie_breaking() -> None:
    """Residual quantum allocation uses finite incremental gain and deterministic alphabetical tie-breaking."""
    from app.integrations.sandbox.s_alloc_core import optimize_budget

    res = optimize_budget(
        budget=10.01,
        channels=["beta", "alpha"],
        min_spend={"alpha": 0.0, "beta": 0.0},
        max_spend={"alpha": 10.0, "beta": 10.0},
        initial_slopes={"alpha": 3.0, "beta": 3.0},
        saturation_spends={"alpha": 5.0, "beta": 5.0},
        currency_precision=2,
    )
    assert res["status"] == "success"
    assert res["allocated_total"] == 10.01
    assert res["budget_residual"] == 0.0
    allocs = res["allocations"]
    assert allocs["alpha"] == 5.01
    assert allocs["beta"] == 5.00


def test_allocation_mroi_floor_stops_discretionary_spend() -> None:
    """Allocation above minimums stops when marginal ROI falls below mroi_floor."""
    from app.integrations.sandbox.s_alloc_core import optimize_budget

    res = optimize_budget(
        budget=1000.0,
        channels=["meta"],
        min_spend={"meta": 100.0},
        max_spend={"meta": 1000.0},
        initial_slopes={"meta": 4.0},
        saturation_spends={"meta": 100.0},
        mroi_floor=1.0,  # At spend=100, R'(100) = 4 / (1 + 100/100)^2 = 4 / 4 = 1.0. Beyond 100, R' < 1.0.
        currency_precision=2,
    )
    assert res["status"] == "success"
    assert res["allocations"]["meta"] == 100.0
    assert res["budget_residual"] == 900.0


def test_allocation_unsupported_model_negative_slope() -> None:
    """Negative or non-finite model parameters return UNSUPPORTED_MODEL."""
    from app.integrations.sandbox.s_alloc_core import optimize_budget
    from app.schemas.strategy import SAllocDomainStatus

    res = optimize_budget(
        budget=100.0,
        channels=["meta"],
        min_spend={"meta": 0.0},
        max_spend={"meta": 100.0},
        initial_slopes={"meta": -2.0},
        saturation_spends={"meta": 50.0},
    )
    assert res["status"] == "error"
    assert res["domain_status"] == SAllocDomainStatus.UNSUPPORTED_MODEL.value


# =============================================================================
# 4. Advisory Subagent Reasoning Contract
# =============================================================================


@pytest.mark.asyncio
async def test_allocation_subagent_advisory_reasoning() -> None:
    """StrategyAllocationAgent produces validated advisory reasoning output without executing sandbox."""
    agent = StrategyAllocationAgent()
    grant = TaskGrant(
        task_id="task-alloc-subagent",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-glow", allowed_channels=["meta", "google"]),
        brand_id="brand-glow",
        objective="propose allocation",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {
        "budget_ceiling": 25000.0,
        "channels": ["meta", "google"],
        "claims": ["hydration_proven"],
    }
    output, metadata = await agent.reason(grant, context)
    assert isinstance(output, AllocationReasoningOutput)
    assert output.scenario_emphasis in ("balanced", "aggressive", "conservative")
    assert len(output.kpi_priorities) > 0
    assert "profile_id" in metadata
    assert metadata["profile_id"] == "w_strat.s_alloc.v1"
