"""Unit tests for T2: Formalize Strategy Engine Pydantic Contracts.

Verifies strict Pydantic-v2 validation, channel-scope invariants, budget bounds,
JSON round-trips, and backward-compatible integration with EvidenceEnvelope and StrategyAgent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.agents.strategy_engine.strategy import StrategyAgent
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import (
    ChannelAllocation,
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.strategy import (
    AllocationConstraint,
    ChannelSpendProposal,
    StrategyDirective,
    StrategyResultEnvelope,
)


def test_allocation_constraint_valid() -> None:
    c = AllocationConstraint(
        channel="  Meta  ",
        min_spend=1000.0,
        max_spend=5000.0,
        min_share=0.1,
        max_share=0.5,
    )
    assert c.channel == "meta"
    assert c.min_spend == 1000.0
    assert c.max_spend == 5000.0
    assert c.min_share == 0.1
    assert c.max_share == 0.5


def test_allocation_constraint_invalid_bounds() -> None:
    # min_spend > max_spend
    with pytest.raises(ValidationError, match="min_spend.*cannot exceed max_spend"):
        AllocationConstraint(channel="meta", min_spend=6000.0, max_spend=5000.0)

    # min_share > max_share
    with pytest.raises(ValidationError, match="min_share.*cannot exceed max_share"):
        AllocationConstraint(channel="meta", min_share=0.8, max_share=0.2)

    # negative min_spend
    with pytest.raises(ValidationError):
        AllocationConstraint(channel="meta", min_spend=-10.0)

    # share outside [0, 1]
    with pytest.raises(ValidationError):
        AllocationConstraint(channel="meta", max_share=1.5)

    # empty channel
    with pytest.raises(ValidationError, match="Channel name cannot be empty"):
        AllocationConstraint(channel="   ")

    # extra fields forbidden
    with pytest.raises(ValidationError):
        AllocationConstraint(channel="meta", unauthorized_field="bad")  # type: ignore[call-arg]


def test_channel_spend_proposal_valid_and_aliases() -> None:
    p = ChannelSpendProposal(
        channel="Google",
        allocated_amount=15000.0,
        percentage_of_total=30.0,
        role="Intent capture",
    )
    assert p.channel == "google"
    assert p.allocated_amount == 15000.0
    assert p.spend == 15000.0
    assert p.percentage_of_total == 30.0
    assert p.percentage == 30.0

    # Test populate_by_name alias
    p2 = ChannelSpendProposal(
        channel="meta",
        spend=25000.0,
        percentage=50.0,
    )
    assert p2.allocated_amount == 25000.0
    assert p2.percentage_of_total == 50.0

    # Conversion to canonical ChannelAllocation
    ca = p.to_channel_allocation()
    assert isinstance(ca, ChannelAllocation)
    assert ca.channel == "google"
    assert ca.allocated_amount == 15000.0
    assert ca.percentage_of_total == 30.0


def test_channel_spend_proposal_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", spend=-100.0, percentage=50.0)

    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", spend=100.0, percentage=150.0)

    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", spend=100.0, percentage=-5.0)

    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", spend=100.0, percentage=10.0, extra="forbid")  # type: ignore[call-arg]


def test_strategy_directive_valid_and_channel_normalization() -> None:
    d = StrategyDirective(
        task_id="task-01",
        tenant_id="tenant-acme",
        budget_ceiling=50000.0,
        authorized_channels=[" Meta ", "google", "meta", "TIKTOK "],
        allocation_constraints=[
            AllocationConstraint(channel="meta", min_spend=10000.0, max_spend=30000.0),
            AllocationConstraint(channel="google", min_spend=5000.0),
        ],
    )
    assert d.authorized_channels == ["meta", "google", "tiktok"]
    assert len(d.allocation_constraints) == 2


def test_strategy_directive_channel_scope_and_budget_violations() -> None:
    # Constraint on unauthorized channel
    with pytest.raises(ValidationError, match="unauthorized channel 'linkedin'"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=50000.0,
            authorized_channels=["meta", "google"],
            allocation_constraints=[AllocationConstraint(channel="linkedin", min_spend=5000.0)],
        )

    # Duplicate constraint for same channel
    with pytest.raises(ValidationError, match="Duplicate allocation constraint"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=50000.0,
            authorized_channels=["meta", "google"],
            allocation_constraints=[
                AllocationConstraint(channel="meta", min_spend=5000.0),
                AllocationConstraint(channel="meta", min_spend=10000.0),
            ],
        )

    # Single min_spend exceeds budget ceiling
    with pytest.raises(ValidationError, match="exceeds total budget ceiling"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            allocation_constraints=[AllocationConstraint(channel="meta", min_spend=15000.0)],
        )

    # Sum of min_spends exceeds budget ceiling
    with pytest.raises(ValidationError, match="Sum of constraint min_spend values"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=["meta", "google"],
            allocation_constraints=[
                AllocationConstraint(channel="meta", min_spend=6000.0),
                AllocationConstraint(channel="google", min_spend=6000.0),
            ],
        )

    # Sum of min_shares exceeds 1.0
    with pytest.raises(ValidationError, match="Sum of constraint min_share values.*exceeds 1.0"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=["meta", "google"],
            allocation_constraints=[
                AllocationConstraint(channel="meta", min_share=0.6),
                AllocationConstraint(channel="google", min_share=0.5),
            ],
        )

    # Empty authorized channels
    with pytest.raises(ValidationError):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=[],
        )

    # Whitespace-only channels
    with pytest.raises(
        ValidationError, match="Channel name in authorized_channels cannot be empty"
    ):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=["   "],
        )

    # Prior ROAS for unauthorized channel
    with pytest.raises(ValidationError, match="Prior ROAS references unauthorized channel"):
        StrategyDirective(
            task_id="task-01",
            tenant_id="tenant-acme",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            prior_roas={"unauthorized_ch": 3.5},
        )


def test_strategy_directive_from_grant() -> None:
    grant = TaskGrant(
        task_id="task-grant-01",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google", "tiktok"]),
        brand_id="brand-glow",
        objective="Drive high-margin customer acquisition",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        policy_constraints=["ftc_disclosure_mandatory"],
        cts_state={"budget_cap": 25000.0},
    )
    context = {
        "budget": 30000.0,  # Should be capped by cts_state budget_cap (25000.0)
        "channels": ["meta", "google", "unauthorized_ext"],
        "allocation_constraints": [
            {"channel": "meta", "min_spend": 5000.0, "max_spend": 15000.0}
        ],
        "prior_roas_meta": 4.2,
    }

    directive = StrategyDirective.from_grant(grant, context)
    assert directive.task_id == "task-grant-01"
    assert directive.tenant_id == "acme"
    assert directive.brand_id == "brand-glow"
    assert directive.budget_ceiling == 25000.0
    assert directive.authorized_channels == ["meta", "google"]
    assert len(directive.allocation_constraints) == 1
    assert directive.allocation_constraints[0].channel == "meta"
    assert directive.allocation_constraints[0].min_spend == 5000.0
    assert directive.prior_roas == {"meta": 4.2}


def test_strategy_result_envelope_invariants_and_compatibility() -> None:
    ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
    plan = OmnichannelStrategyPlan(
        plan_id="plan-01",
        tenant_id="acme",
        brand_id="brand-01",
        budget_ceiling=50000.0,
        total_allocated=48000.0,
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=30000.0, percentage_of_total=60.0),
            ChannelAllocation(channel="google", allocated_amount=18000.0, percentage_of_total=36.0),
        ],
    )

    env = StrategyResultEnvelope(
        task_id="task-01",
        worker_role=WorkerRole.STRATEGY,
        confidence=ci,
        strategy_plan=plan,
        channel_proposals=[
            ChannelSpendProposal(channel="meta", spend=30000.0, percentage=60.0),
            ChannelSpendProposal(channel="google", spend=18000.0, percentage=36.0),
        ],
    )
    # Liskov substitution / compatibility
    assert isinstance(env, EvidenceEnvelope)
    base_env = env.to_evidence_envelope()
    assert type(base_env) is EvidenceEnvelope
    assert base_env.task_id == "task-01"

    # From raw EvidenceEnvelope extraction
    raw_env = EvidenceEnvelope(
        task_id="task-02",
        worker_role=WorkerRole.STRATEGY,
        confidence=ci,
        payload={"strategy_plan": plan.model_dump_json()},
    )
    derived_env = StrategyResultEnvelope.from_evidence_envelope(raw_env)
    assert derived_env.strategy_plan is not None
    assert derived_env.strategy_plan.plan_id == "plan-01"
    assert len(derived_env.channel_proposals) == 2
    assert derived_env.channel_proposals[0].channel == "meta"


def test_strategy_result_envelope_invalid_output_bounds() -> None:
    ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)

    # Overallocated plan exceeds budget ceiling
    bad_plan = OmnichannelStrategyPlan(
        plan_id="plan-bad",
        tenant_id="acme",
        brand_id="brand-01",
        budget_ceiling=10000.0,
        total_allocated=15000.0,
    )
    with pytest.raises(ValidationError, match="total_allocated.*exceeds.*budget_ceiling"):
        StrategyResultEnvelope(
            task_id="task-bad",
            worker_role=WorkerRole.STRATEGY,
            confidence=ci,
            strategy_plan=bad_plan,
        )

    # Channel proposals exceed budget ceiling
    ok_plan = OmnichannelStrategyPlan(
        plan_id="plan-ok",
        tenant_id="acme",
        brand_id="brand-01",
        budget_ceiling=10000.0,
        total_allocated=9000.0,
    )
    with pytest.raises(
        ValidationError, match="Sum of channel spend proposals.*exceeds budget ceiling"
    ):
        StrategyResultEnvelope(
            task_id="task-bad-props",
            worker_role=WorkerRole.STRATEGY,
            confidence=ci,
            strategy_plan=ok_plan,
            channel_proposals=[
                ChannelSpendProposal(channel="meta", spend=7000.0, percentage=70.0),
                ChannelSpendProposal(channel="google", spend=6000.0, percentage=60.0),
            ],
        )

    # Inverted confidence interval
    bad_ci = ConfidenceInterval(point_estimate=0.5, lower_bound=0.8, upper_bound=0.2)
    with pytest.raises(ValidationError, match="Invalid confidence interval"):
        StrategyResultEnvelope(
            task_id="task-bad-ci",
            worker_role=WorkerRole.STRATEGY,
            confidence=bad_ci,
        )


def test_pydantic_json_round_trips() -> None:
    c = AllocationConstraint(
        channel="tiktok", min_spend=500.0, max_spend=2000.0, min_share=0.05, max_share=0.2
    )
    c_json = c.model_dump_json()
    assert AllocationConstraint.model_validate_json(c_json) == c

    p = ChannelSpendProposal(channel="tiktok", spend=1200.0, percentage=12.0)
    p_json = p.model_dump_json()
    assert ChannelSpendProposal.model_validate_json(p_json) == p

    d = StrategyDirective(
        task_id="task-json-01",
        tenant_id="acme",
        budget_ceiling=20000.0,
        authorized_channels=["tiktok", "meta"],
        allocation_constraints=[c],
    )
    d_json = d.model_dump_json()
    assert StrategyDirective.model_validate_json(d_json) == d


@pytest.mark.asyncio
async def test_strategy_agent_run_emits_validated_strategy_result_envelope() -> None:
    sandbox = SandboxClient()
    agent = StrategyAgent(sandbox_client=sandbox)

    grant = TaskGrant(
        task_id="task-strat-live",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme_wellness", allowed_channels=["meta", "google"]),
        brand_id="acme_glow",
        objective="Drive scalable omnichannel ROI",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {
        "budget": 20000.0,
        "channels": ["meta", "google"],
        "claims_dossier": {
            "tenant_id": "acme_wellness",
            "claims": [{"text": "Hydrates skin", "validation_status": "SUPPORTED"}],
        },
        "customer_voice_analysis": {
            "tenant_id": "acme_wellness",
            "objection_profiles": [{"theme": "price", "frequency": 5}],
        },
        "competitor_intelligence": {
            "tenant_id": "acme_wellness",
            "competitor": "Rival",
            "benchmark_price": "49.99",
        },
    }

    envelope = await agent.run(grant, context)

    # Asserts returned envelope is an instance of both StrategyResultEnvelope and EvidenceEnvelope
    assert isinstance(envelope, StrategyResultEnvelope)
    assert isinstance(envelope, EvidenceEnvelope)
    assert envelope.task_id == "task-strat-live"
    assert envelope.strategy_plan is not None
    assert envelope.strategy_plan.total_allocated <= 20000.0
    assert len(envelope.channel_proposals) >= 1
    for cp in envelope.channel_proposals:
        assert cp.allocated_amount >= 0.0
        assert 0.0 <= cp.percentage_of_total <= 100.0
