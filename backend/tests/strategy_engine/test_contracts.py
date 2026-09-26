"""Tests for Strategy Engine Pydantic-v2 domain contracts (T2).

Validates AllocationConstraint, ChannelSpendProposal, StrategyDirective,
and StrategyResultEnvelope including boundaries, invariants, serialization,
and bidirectional compatibility with TaskGrant/EvidenceEnvelope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.agent_contracts import (
    ChannelAllocation,
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.strategy import (
    AllocationConstraint,
    ChannelSpendProposal,
    StrategyDirective,
    StrategyResultEnvelope,
)


# =============================================================================
# 1. AllocationConstraint Tests
# =============================================================================


def test_allocation_constraint_valid() -> None:
    """Valid constraints normalize channel and preserve valid bounds."""
    c = AllocationConstraint(
        channel="  META ",
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
    """AllocationConstraint rejects min_spend > max_spend or min_share > max_share."""
    with pytest.raises(ValidationError, match="min_spend .* cannot exceed max_spend"):
        AllocationConstraint(channel="meta", min_spend=5000.0, max_spend=1000.0)

    with pytest.raises(ValidationError, match="min_share .* cannot exceed max_share"):
        AllocationConstraint(channel="google", min_share=0.6, max_share=0.3)


def test_allocation_constraint_empty_channel_and_extra_fields() -> None:
    """AllocationConstraint rejects empty channel and extra fields."""
    with pytest.raises(ValidationError):
        AllocationConstraint(channel="   ")

    with pytest.raises(ValidationError):
        AllocationConstraint(channel="meta", extra_prop="disallowed")  # type: ignore[call-arg]


# =============================================================================
# 2. ChannelSpendProposal Tests
# =============================================================================


def test_channel_spend_proposal_valid_and_aliases() -> None:
    """ChannelSpendProposal normalizes channel and supports spend/percentage aliases."""
    prop = ChannelSpendProposal(
        channel="Google",
        allocated_amount=12000.0,
        percentage_of_total=40.0,
        role="Intent Capture",
        primary_kpi="CAC / ROAS",
        prior_roas=3.8,
        target_roas_range=(3.2, 4.4),
        constraints=["target_cac_lt_60"],
    )
    assert prop.channel == "google"
    assert prop.spend == 12000.0
    assert prop.percentage == 40.0
    assert prop.role == "Intent Capture"
    assert prop.prior_roas == 3.8

    # Alias construction
    prop_alias = ChannelSpendProposal(
        channel="meta",
        spend=8000.0,  # type: ignore[call-arg]
        percentage=26.67,  # type: ignore[call-arg]
    )
    assert prop_alias.allocated_amount == 8000.0
    assert prop_alias.percentage_of_total == 26.67


def test_channel_spend_proposal_to_channel_allocation() -> None:
    """Conversion to canonical agent_contracts.ChannelAllocation."""
    prop = ChannelSpendProposal(
        channel="tiktok",
        spend=5000.0,  # type: ignore[call-arg]
        percentage=16.67,  # type: ignore[call-arg]
        role="Awareness",
        primary_kpi="CPM / Reach",
    )
    ca = prop.to_channel_allocation()
    assert isinstance(ca, ChannelAllocation)
    assert ca.channel == "tiktok"
    assert ca.allocated_amount == 5000.0
    assert ca.percentage_of_total == 16.67


def test_channel_spend_proposal_invalid() -> None:
    """Negative spend or invalid percentage triggers validation errors."""
    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", allocated_amount=-500.0, percentage_of_total=20.0)

    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", allocated_amount=500.0, percentage_of_total=120.0)


# =============================================================================
# 3. StrategyDirective Tests
# =============================================================================


def test_strategy_directive_construction_and_bounds() -> None:
    """StrategyDirective enforces budget ceiling, channel authorization, and serialization."""
    d = StrategyDirective(
        task_id="task-strat-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        objective="Drive qualified acquisition",
        budget_ceiling=50000.0,
        authorized_channels=["meta", "google", "tiktok"],
        allocation_constraints=[
            AllocationConstraint(channel="meta", min_spend=5000.0, max_spend=25000.0)
        ],
        prior_roas={"meta": 4.0, "google": 3.5},
    )
    assert d.budget_ceiling == 50000.0
    assert "tiktok" in d.authorized_channels

    # Serialization round-trip
    dumped = d.model_dump(mode="json")
    loaded = StrategyDirective.model_validate(dumped)
    assert loaded == d


def test_strategy_directive_unauthorized_channel_rejected() -> None:
    """Constraints or priors referencing unauthorized channels raise ValueError."""
    with pytest.raises(ValidationError, match="unauthorized channel"):
        StrategyDirective(
            task_id="task-strat-bad",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            allocation_constraints=[AllocationConstraint(channel="unauthorized_network")],
        )

    with pytest.raises(ValidationError, match="unauthorized channel"):
        StrategyDirective(
            task_id="task-strat-bad-roas",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            prior_roas={"unauthorized_channel": 2.5},
        )


def test_strategy_directive_negative_budget_rejected() -> None:
    """Negative budget ceiling is rejected."""
    with pytest.raises(ValidationError):
        StrategyDirective(
            task_id="task-neg-budget",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=-1000.0,
            authorized_channels=["meta"],
        )


def test_strategy_directive_from_grant_compatibility() -> None:
    """StrategyDirective derives cleanly from IE TaskGrant and context."""
    grant = TaskGrant(
        task_id="task-grant-strat",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-beta", allowed_channels=["meta", "google"]),
        brand_id="brand-beta",
        objective="propose allocation",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        cts_state={"budget_cap": 20000.0},
    )
    context = {
        "budget": 25000.0,  # Must be clamped by cts_state budget_cap (20000.0)
        "channels": ["meta", "google", "disallowed_ch"],
        "prior_roas_meta": 4.5,
    }
    directive = StrategyDirective.from_grant(grant, context)
    assert directive.task_id == "task-grant-strat"
    assert directive.tenant_id == "tenant-beta"
    assert directive.budget_ceiling == 20000.0
    assert directive.authorized_channels == ["meta", "google"]
    assert directive.prior_roas.get("meta") == 4.5


# =============================================================================
# 4. StrategyResultEnvelope Tests
# =============================================================================


def test_strategy_result_envelope_valid() -> None:
    """StrategyResultEnvelope valid construction and downcast to EvidenceEnvelope."""
    plan = OmnichannelStrategyPlan(
        plan_id="plan-valid-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        total_allocated=15000.0,
        budget_ceiling=20000.0,
        expected_blended_roas=3.6,
        confidence_score=0.82,
        primary_channel="meta",
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=10000.0, percentage_of_total=66.7),
            ChannelAllocation(channel="google", allocated_amount=5000.0, percentage_of_total=33.3),
        ],
    )
    envelope = StrategyResultEnvelope(
        task_id="task-res-01",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.82, lower_bound=0.70, upper_bound=0.92),
        evidence=["Blended ROAS: 3.6x"],
        findings=["Optimal media mix identified"],
        strategy_plan=plan,
        channel_proposals=[
            ChannelSpendProposal(channel="meta", spend=10000.0, percentage=66.7),  # type: ignore[call-arg]
            ChannelSpendProposal(channel="google", spend=5000.0, percentage=33.3),  # type: ignore[call-arg]
        ],
    )
    assert envelope.worker_role == WorkerRole.STRATEGY
    assert envelope.strategy_plan is not None
    assert envelope.strategy_plan.total_allocated == 15000.0

    # Downcast to base EvidenceEnvelope
    base_env = envelope.to_evidence_envelope()
    assert isinstance(base_env, EvidenceEnvelope)
    assert base_env.task_id == "task-res-01"


def test_strategy_result_envelope_budget_exceeded_rejected() -> None:
    """Total allocation exceeding budget ceiling raises ValidationError."""
    plan = OmnichannelStrategyPlan(
        plan_id="plan-bad-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        total_allocated=25000.0,
        budget_ceiling=20000.0,  # Exceeded!
        expected_blended_roas=3.0,
        confidence_score=0.8,
        primary_channel="meta",
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=25000.0, percentage_of_total=100.0),
        ],
    )
    with pytest.raises(ValidationError, match="exceeds budget_ceiling"):
        StrategyResultEnvelope(
            task_id="task-res-bad",
            worker_role=WorkerRole.STRATEGY,
            confidence=ConfidenceInterval(point_estimate=0.8, lower_bound=0.6, upper_bound=0.9),
            strategy_plan=plan,
        )


def test_strategy_result_envelope_invalid_confidence_rejected() -> None:
    """Confidence interval ordering violations are rejected."""
    with pytest.raises(ValidationError, match="Invalid confidence interval"):
        StrategyResultEnvelope(
            task_id="task-res-conf-bad",
            worker_role=WorkerRole.STRATEGY,
            confidence=ConfidenceInterval(point_estimate=0.5, lower_bound=0.8, upper_bound=0.9),
        )
