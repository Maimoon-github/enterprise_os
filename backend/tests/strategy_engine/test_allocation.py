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
    """Impossible constraints (e.g. min spend exceeding total budget) fail closed or report warning."""
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
    # S_ALLOC must either fail closed or clamp to budget ceiling
    if result["status"] == "success":
        plan = json.loads(result["strategy_plan"])
        assert plan["total_allocated"] <= 10000.0


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
