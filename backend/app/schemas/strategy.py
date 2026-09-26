"""W_STRAT Strategy Engine typed Pydantic-v2 domain contracts (T2).

Provides strictly validated boundary contracts for Strategy input normalization
and output validation:
- AllocationConstraint: Channel-scoped budget and share boundary constraints.
- ChannelSpendProposal: Typed spend proposal genuinely emitted/derivable from S_ALLOC.
- StrategyDirective: Normalized W_STRAT execution directive derived from IE TaskGrant.
- StrategyResultEnvelope: Typed Strategy result envelope compatible with EvidenceEnvelope.
"""

from __future__ import annotations

import contextlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.agent_contracts import (
    ChannelAllocation,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)


class AllocationConstraint(BaseModel):
    """Channel-scoped budget and share boundary constraints."""

    model_config = ConfigDict(extra="forbid", strict=True)

    channel: str = Field(..., min_length=1)
    min_spend: float = Field(default=0.0, ge=0.0)
    max_spend: float | None = Field(default=None, ge=0.0)
    min_share: float = Field(default=0.0, ge=0.0, le=1.0)
    max_share: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Channel name cannot be empty or whitespace.")
        return cleaned

    @model_validator(mode="after")
    def validate_bounds(self) -> AllocationConstraint:
        if self.max_spend is not None and self.min_spend > self.max_spend:
            raise ValueError(
                f"min_spend ({self.min_spend}) cannot exceed max_spend ({self.max_spend}) "
                f"for channel '{self.channel}'"
            )
        if self.min_share > self.max_share:
            raise ValueError(
                f"min_share ({self.min_share}) cannot exceed max_share ({self.max_share}) "
                f"for channel '{self.channel}'"
            )
        return self


class ChannelSpendProposal(BaseModel):
    """Channel-specific budget allocation proposal genuinely emitted by S_ALLOC."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    channel: str = Field(..., min_length=1)
    allocated_amount: float = Field(..., ge=0.0, alias="spend")
    percentage_of_total: float = Field(..., ge=0.0, le=100.0, alias="percentage")
    role: str = ""
    primary_kpi: str = "mROI / incremental KPI"
    prior_roas: float | None = None
    target_roas_range: tuple[float, float] | None = None
    constraints: list[str] = Field(default_factory=list)

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Channel name cannot be empty or whitespace.")
        return cleaned

    @property
    def spend(self) -> float:
        """Alias for allocated_amount."""
        return self.allocated_amount

    @property
    def percentage(self) -> float:
        """Alias for percentage_of_total."""
        return self.percentage_of_total

    def to_channel_allocation(self) -> ChannelAllocation:
        """Convert to canonical agent_contracts.ChannelAllocation."""
        return ChannelAllocation(
            channel=self.channel,
            allocated_amount=self.allocated_amount,
            percentage_of_total=self.percentage_of_total,
            role=self.role,
            primary_kpi=self.primary_kpi,
            prior_roas=self.prior_roas,
            target_roas_range=self.target_roas_range,
            constraints=self.constraints,
        )


class StrategyDirective(BaseModel):
    """Typed normalized Strategy input derived from IE TaskGrant and bounded context."""

    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    brand_id: str = Field(default="default", min_length=1)
    objective: str = Field(
        default="propose_omnichannel_strategy_and_media_allocation", min_length=1
    )
    budget_ceiling: float = Field(..., ge=0.0)
    authorized_channels: list[str] = Field(..., min_length=1)
    time_horizon: str = Field(default="90_days", min_length=1)
    allocation_constraints: list[AllocationConstraint] = Field(default_factory=list)

    # Scoped evidence and context slices
    approved_claims: list[dict[str, Any]] = Field(default_factory=list)
    objections: list[dict[str, Any]] = Field(default_factory=list)
    competitor_signals: dict[str, Any] = Field(default_factory=dict)
    policy_constraints: list[str] = Field(default_factory=list)
    kpi_name: str | None = None
    mroi_floor: float = 0.0
    scenario_emphasis: Literal["balanced", "aggressive", "conservative"] = "balanced"
    prior_roas: dict[str, float] = Field(default_factory=dict)

    @field_validator("authorized_channels")
    @classmethod
    def normalize_channels(cls, channels: list[str]) -> list[str]:
        cleaned: list[str] = []
        for ch in channels:
            c = ch.strip().lower()
            if not c:
                raise ValueError("Channel name in authorized_channels cannot be empty.")
            if c not in cleaned:
                cleaned.append(c)
        if not cleaned:
            raise ValueError("authorized_channels must contain at least one valid channel.")
        return cleaned

    @model_validator(mode="after")
    def validate_channel_and_constraint_invariants(self) -> StrategyDirective:
        seen_channels: set[str] = set()
        total_min_spend = 0.0
        total_min_share = 0.0
        authorized_set = set(self.authorized_channels)

        for c in self.allocation_constraints:
            if c.channel not in authorized_set:
                raise ValueError(
                    f"Allocation constraint references unauthorized channel '{c.channel}'. "
                    f"Authorized channels: {self.authorized_channels}"
                )
            if c.channel in seen_channels:
                raise ValueError(f"Duplicate allocation constraint for channel '{c.channel}'")
            seen_channels.add(c.channel)

            if c.min_spend > self.budget_ceiling:
                raise ValueError(
                    f"min_spend ({c.min_spend}) for channel '{c.channel}' "
                    f"exceeds total budget ceiling ({self.budget_ceiling})"
                )

            total_min_spend += c.min_spend
            total_min_share += c.min_share

        if total_min_spend > self.budget_ceiling + 1e-6:
            raise ValueError(
                f"Sum of constraint min_spend values ({total_min_spend}) "
                f"exceeds budget ceiling ({self.budget_ceiling})"
            )
        if total_min_share > 1.0 + 1e-6:
            raise ValueError(
                f"Sum of constraint min_share values ({total_min_share}) exceeds 1.0 (100%)"
            )

        for ch in self.prior_roas:
            if ch not in authorized_set:
                raise ValueError(
                    f"Prior ROAS references unauthorized channel '{ch}'. "
                    f"Authorized channels: {self.authorized_channels}"
                )

        return self

    @classmethod
    def from_grant(
        cls, grant: TaskGrant, context: dict[str, Any] | None = None
    ) -> StrategyDirective:
        """Derive and validate a StrategyDirective from an authorized IE TaskGrant."""
        ctx = context or {}
        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        brand_id = grant.brand_id or "default"
        objective = (grant.objective or "propose_omnichannel_strategy_and_media_allocation").strip()

        # 1. Budget normalization
        raw_budget = (
            ctx.get("budget_ceiling")
            or ctx.get("budget_cap")
            or ctx.get("budget")
            or grant.cts_state.get("budget_cap")
            or (grant.budget_breakdown.get("spend") if grant.budget_breakdown else None)
            or 10000.0
        )
        try:
            budget_ceiling = float(raw_budget)
            if budget_ceiling < 0.0:
                raise ValueError(f"Budget ceiling cannot be negative: {budget_ceiling}")
        except (ValueError, TypeError) as err:
            if "negative" in str(err):
                raise
            budget_ceiling = 10000.0

        if grant.cts_state.get("budget_cap") is not None:
            try:
                grant_cap = float(grant.cts_state["budget_cap"])
                if grant_cap >= 0.0:
                    budget_ceiling = min(budget_ceiling, grant_cap)
            except (ValueError, TypeError):
                pass

        # 2. Channels normalization
        tenant_allowed = (
            [c.strip().lower() for c in grant.tenant_scope.allowed_channels if c.strip()]
            if grant.tenant_scope and grant.tenant_scope.allowed_channels
            else []
        )
        context_channels = ctx.get("channels")
        requested_channels: list[str] = []
        if context_channels:
            if isinstance(context_channels, list):
                requested_channels = [
                    str(c).strip().lower() for c in context_channels if str(c).strip()
                ]
            elif isinstance(context_channels, str):
                requested_channels = [
                    c.strip().lower() for c in context_channels.split(",") if c.strip()
                ]

        if tenant_allowed and requested_channels:
            allowed_channels = [c for c in requested_channels if c in tenant_allowed]
            if not allowed_channels:
                allowed_channels = list(tenant_allowed)
        elif tenant_allowed:
            allowed_channels = list(tenant_allowed)
        elif requested_channels:
            allowed_channels = requested_channels
        else:
            allowed_channels = ["meta", "google", "tiktok", "linkedin"]

        time_horizon = str(
            ctx.get("time_horizon", grant.cts_state.get("time_horizon", "90_days"))
        )

        # 3. Allocation constraints normalization
        constraints: list[AllocationConstraint] = []
        raw_constraints = ctx.get("allocation_constraints") or ctx.get("channel_constraints")
        if isinstance(raw_constraints, list):
            for rc in raw_constraints:
                if isinstance(rc, AllocationConstraint):
                    constraints.append(rc)
                elif isinstance(rc, dict):
                    constraints.append(AllocationConstraint.model_validate(rc))
        elif isinstance(raw_constraints, dict):
            for ch_key, ch_val in raw_constraints.items():
                if isinstance(ch_val, dict):
                    data = dict(ch_val)
                    data.setdefault("channel", ch_key)
                    constraints.append(AllocationConstraint.model_validate(data))

        # 4. Optional priors
        priors: dict[str, float] = {}
        for ch in allowed_channels:
            prior_key = f"prior_roas_{ch}"
            if prior_key in ctx:
                with contextlib.suppress(ValueError, TypeError):
                    priors[ch] = float(ctx[prior_key])

        return cls(
            task_id=grant.task_id,
            tenant_id=tenant_id,
            brand_id=brand_id,
            objective=objective,
            budget_ceiling=budget_ceiling,
            authorized_channels=allowed_channels,
            time_horizon=time_horizon,
            allocation_constraints=constraints,
            policy_constraints=list(grant.policy_constraints),
            kpi_name=ctx.get("kpi_name"),
            mroi_floor=float(ctx.get("mroi_floor", 0.0)),
            prior_roas=priors,
        )


class StrategyResultEnvelope(EvidenceEnvelope):
    """Typed Strategy result envelope compatible with EvidenceEnvelope."""

    strategy_plan: OmnichannelStrategyPlan | None = None
    channel_proposals: list[ChannelSpendProposal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strategy_outputs(self) -> StrategyResultEnvelope:
        if (
            self.confidence.lower_bound > self.confidence.point_estimate
            or self.confidence.point_estimate > self.confidence.upper_bound
        ):
            raise ValueError(
                f"Invalid confidence interval: [{self.confidence.lower_bound}, "
                f"{self.confidence.point_estimate}, {self.confidence.upper_bound}]"
            )

        if self.strategy_plan is not None:
            if self.strategy_plan.total_allocated < 0.0:
                raise ValueError("strategy_plan.total_allocated cannot be negative.")
            if self.strategy_plan.total_allocated > self.strategy_plan.budget_ceiling + 0.01:
                raise ValueError(
                    f"strategy_plan.total_allocated ({self.strategy_plan.total_allocated}) exceeds "
                    f"budget_ceiling ({self.strategy_plan.budget_ceiling})"
                )

            if self.channel_proposals:
                total_prop = sum(p.allocated_amount for p in self.channel_proposals)
                if total_prop > self.strategy_plan.budget_ceiling + 0.01:
                    raise ValueError(
                        f"Sum of channel spend proposals ({total_prop}) exceeds "
                        f"budget ceiling ({self.strategy_plan.budget_ceiling})"
                    )

        return self

    @classmethod
    def from_evidence_envelope(cls, env: EvidenceEnvelope) -> StrategyResultEnvelope:
        """Construct and validate StrategyResultEnvelope from an EvidenceEnvelope."""
        data = env.model_dump()
        strategy_plan: OmnichannelStrategyPlan | None = None
        channel_proposals: list[ChannelSpendProposal] = []

        raw_plan = env.payload.get("strategy_plan")
        if raw_plan:
            try:
                if isinstance(raw_plan, str):
                    strategy_plan = OmnichannelStrategyPlan.model_validate_json(raw_plan)
                elif isinstance(raw_plan, dict):
                    strategy_plan = OmnichannelStrategyPlan.model_validate(raw_plan)
            except Exception:
                strategy_plan = None

        if strategy_plan and strategy_plan.channel_allocations:
            for ca in strategy_plan.channel_allocations:
                channel_proposals.append(
                    ChannelSpendProposal(
                        channel=ca.channel,
                        allocated_amount=ca.allocated_amount,
                        percentage_of_total=ca.percentage_of_total,
                        role=ca.role,
                        primary_kpi=ca.primary_kpi,
                        prior_roas=ca.prior_roas,
                        target_roas_range=ca.target_roas_range,
                        constraints=ca.constraints,
                    )
                )

        data["strategy_plan"] = strategy_plan
        data["channel_proposals"] = channel_proposals
        return cls(**data)

    def to_evidence_envelope(self) -> EvidenceEnvelope:
        """Downcast to base EvidenceEnvelope for generic consumers."""
        data = self.model_dump(exclude={"strategy_plan", "channel_proposals"})
        return EvidenceEnvelope.model_validate(data)
