"""Tests for LP-05 Measurement Specialists: Attribution, Incrementality, Fatigue, Decay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.agents.learning_performance_engine.subagents import (
    LearningAttributionAgent,
    LearningDecayAgent,
    LearningFatigueAgent,
    LearningIncrementalityAgent,
)
from app.integrations.sandbox.s_attr_core import (
    compute_attribution_and_roas,
    compute_creative_fatigue,
    compute_incrementality_lift,
    compute_lag_and_decay,
)
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.learning_performance import (
    CalibrationProposal,
    EvidenceCategory,
    SpecialistStatus,
    UncertaintyKind,
)


def _make_grant(task_id: str = "task-t31-analytics", tenant_id: str = "tenant-gamma") -> TaskGrant:
    return TaskGrant(
        grant_id="grant-001",
        task_id=task_id,
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id=tenant_id),
        allowed_operations=["execute_s_attr"],
        rate_limits={"max_rpm": 60},
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        parent_sandbox_id=None,
    )


# --- 1. Attribution & Safe ROAS ---

def test_attribution_reconciliation_and_safe_roas() -> None:
    now = datetime.now(UTC)
    paths = [
        {
            "conversion_id": "c1",
            "revenue": 100.0,
            "occurred_at": now.isoformat(),
            "touchpoints": [
                {"channel": "meta", "campaign_id": "m1"},
                {"channel": "google", "campaign_id": "g1"},
            ],
        },
        {
            "conversion_id": "c2",
            "revenue": 200.0,
            "occurred_at": now.isoformat(),
            "touchpoints": [
                {"channel": "google", "campaign_id": "g1"},
            ],
        },
        {
            "conversion_id": "c3",
            "revenue": 50.0,
            "occurred_at": now.isoformat(),
            "touchpoints": [],  # unmatched / unattributed
        },
    ]
    spend = {
        "meta": 100.0,
        "google": 100.0,
        "tiktok": 0.0,  # Zero spend channel
    }

    res = compute_attribution_and_roas({
        "task_id": "t-attr-1",
        "model_type": "linear",
        "paths": paths,
        "spend_data": spend,
    })

    assert res["status"] == "complete"
    assert res["causal_claim_permitted"] is False
    assert res["inference_category"] == "observational"

    # Reconciliation
    reconc = res["reconciliation"]
    assert reconc["total_revenue"] == 350.0
    assert reconc["unattributed_revenue"] == 50.0
    assert reconc["attributed_revenue"] == 300.0
    assert reconc["total_conversions"] == 3
    assert reconc["unattributed_conversions"] == 1.0

    # ROAS checks
    roas_by_chan = {r["channel"]: r for r in res["roas_metrics"]}
    assert roas_by_chan["meta"]["roas"] == 0.5  # 50 / 100
    assert roas_by_chan["google"]["roas"] == 2.5  # 250 / 100
    # Zero spend channel has None roas, status zero_spend_zero_revenue
    assert roas_by_chan["tiktok"]["roas"] is None
    assert roas_by_chan["tiktok"]["status"] == "zero_spend_zero_revenue"


@pytest.mark.asyncio
async def test_attribution_subagent_run() -> None:
    agent = LearningAttributionAgent()
    grant = _make_grant()
    context = {
        "paths": [
            {"conversion_id": "c1", "revenue": 100.0, "touchpoints": [{"channel": "meta"}]},
        ],
        "spend_data": {"meta": 50.0},
    }
    result = await agent.run(grant, context)
    assert result.status == SpecialistStatus.COMPLETE
    assert result.role == "LEARN-ATTRIBUTION"
    assert len(result.estimates) == 2  # weight + roas
    roas_est = [e for e in result.estimates if e.metric == "roas"][0]
    assert roas_est.point_estimate == 2.0
    assert roas_est.causal_claim_permitted is False


# --- 2. Incrementality & Calibration ---

def test_incrementality_itt_and_calibration() -> None:
    payload = {
        "task_id": "t-inc-1",
        "channel": "meta",
        "source_experiment_id": "exp-meta-q3",
        "treatment_sample_size": 10000,
        "treatment_conversions": 500,
        "control_sample_size": 10000,
        "control_conversions": 400,
    }
    res = compute_incrementality_lift(payload)
    assert res["status"] == "complete"
    assert res["causal_claim_permitted"] is True
    assert res["inference_category"] == "experimental"
    assert res["absolute_lift"] == 0.0100  # 5.0% - 4.0%
    assert res["treatment_rate"] == 0.05
    assert res["control_rate"] == 0.04
    assert res["confidence_interval"]["lower"] < res["absolute_lift"] < res["confidence_interval"]["upper"]

    # Calibration proposal
    cal = res["calibration_proposal"]
    assert cal["applied"] is False
    assert cal["proposed_weight_or_multiplier"] == 0.0100


def test_incrementality_negative_lift_preservation() -> None:
    payload = {
        "task_id": "t-inc-neg",
        "channel": "search",
        "source_experiment_id": "exp-search-q3",
        "treatment_sample_size": 1000,
        "treatment_conversions": 20,  # 2.0%
        "control_sample_size": 1000,
        "control_conversions": 30,  # 3.0%
    }
    res = compute_incrementality_lift(payload)
    assert res["status"] == "complete"
    assert res["absolute_lift"] == -0.0100  # Preserved negative lift!
    assert res["confidence_interval"]["lower"] < -0.0100


@pytest.mark.asyncio
async def test_incrementality_subagent_run() -> None:
    agent = LearningIncrementalityAgent()
    grant = _make_grant()
    context = {
        "channel": "meta",
        "source_experiment_id": "exp-202",
        "treatment_sample_size": 5000,
        "treatment_conversions": 250,
        "control_sample_size": 5000,
        "control_conversions": 200,
    }
    proposal, result = await agent.run(grant, context)
    assert proposal is not None
    assert proposal.applied is False
    assert result.status == SpecialistStatus.COMPLETE
    assert result.role == "LEARN-INCREMENTALITY"
    assert len(result.estimates) == 1
    assert result.estimates[0].causal_claim_permitted is True


# --- 3. Fatigue: Wearout vs Saturation ---

def test_creative_fatigue_wearout_distinction() -> None:
    payload = {
        "task_id": "t-fatigue-1",
        "creatives": [
            {
                "creative_id": "cr-wearout",
                "days_active": 30,
                "reported_roas": 2.5,
                "frequency_trajectory": [1.0, 1.8, 2.5, 3.2],
                "ctr_trajectory": [0.04, 0.035, 0.025, 0.012],  # declining CTR + increasing freq
            },
            {
                "creative_id": "cr-saturation",
                "days_active": 10,
                "reported_roas": 3.0,
                "frequency_trajectory": [1.5, 2.5, 3.5, 4.5],  # high freq saturation
                "ctr_trajectory": [0.03, 0.03, 0.03, 0.029],
            },
        ],
    }
    res = compute_creative_fatigue(payload)
    assert res["status"] == "complete"
    evals = {e["creative_id"]: e for e in res["creative_evaluations"]}

    assert evals["cr-wearout"]["fatigue_detected"] is True
    assert evals["cr-wearout"]["recommended_action"] == "refresh_creative_hooks"

    assert evals["cr-saturation"]["audience_saturation_detected"] is True
    assert evals["cr-saturation"]["recommended_action"] == "broaden_audience"


@pytest.mark.asyncio
async def test_fatigue_subagent_run() -> None:
    agent = LearningFatigueAgent()
    grant = _make_grant()
    context = {
        "creatives": [
            {
                "creative_id": "c-101",
                "days_active": 20,
                "reported_roas": 2.8,
                "frequency_trajectory": [1.0, 1.5, 2.2, 3.0],
                "ctr_trajectory": [0.03, 0.025, 0.02, 0.015],
            }
        ]
    }
    result = await agent.run(grant, context)
    assert result.status == SpecialistStatus.COMPLETE
    assert result.role == "LEARN-FATIGUE"
    assert len(result.estimates) == 1
    assert result.estimates[0].causal_claim_permitted is False


# --- 4. Lag, Saturation, and Decay Boundaries ---

def test_decay_adstock_and_half_life_boundaries() -> None:
    # 1. Standard geometric decay: 0 < alpha < 1
    res1 = compute_lag_and_decay({"alpha": 0.5, "series": [100.0, 0.0, 0.0]})
    assert res1["half_life_status"] == "finite_geometric"
    assert res1["half_life_bins"] == 1.0  # log(0.5)/log(0.5) == 1.0
    assert len(res1["adstock_series"]) == 3
    assert len(res1["hill_series"]) == 3

    # 2. Zero carryover: alpha == 0
    res0 = compute_lag_and_decay({"alpha": 0.0, "series": [100.0, 0.0, 0.0]})
    assert res0["half_life_status"] == "zero_carryover"
    assert res0["half_life_bins"] == 0.0

    # 3. Infinite carryover boundary: alpha == 1.0
    res_inf = compute_lag_and_decay({"alpha": 1.0, "series": [100.0, 0.0, 0.0]})
    assert res_inf["half_life_status"] == "undefined_infinite_carryover"
    assert res_inf["half_life_bins"] is None


@pytest.mark.asyncio
async def test_decay_subagent_run() -> None:
    agent = LearningDecayAgent()
    grant = _make_grant()
    context = {"alpha": 0.25, "series": [100.0, 50.0, 25.0]}
    result = await agent.run(grant, context)
    assert result.status == SpecialistStatus.COMPLETE
    assert result.role == "LEARN-DECAY"
    hl_est = [e for e in result.estimates if e.metric == "half_life"][0]
    assert hl_est.point_estimate == 0.5  # log(0.5)/log(0.25) = 0.5
    assert hl_est.causal_claim_permitted is False
