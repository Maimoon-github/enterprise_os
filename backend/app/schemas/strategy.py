"""W_STRAT Strategy Engine typed Pydantic-v2 domain contracts (T2).

Provides strictly validated boundary contracts for Strategy input normalization
and output validation:
- SAllocDomainStatus: Explicit calculation and domain outcome statuses.
- AllocationConstraint: Channel-scoped budget and share boundary constraints.
- ChannelSpendProposal: Typed spend proposal genuinely emitted/derivable from S_ALLOC.
- StrategyDirective: Normalized W_STRAT execution directive derived from IE TaskGrant.
- StrategyResultEnvelope: Typed Strategy result envelope compatible with EvidenceEnvelope.
- SAllocMandate: Typed execution mandate for S_ALLOC specialist.
- SAllocResult: Typed execution result and diagnostics from S_ALLOC specialist.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    ChannelAllocation,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.sandbox import (
    SandboxExecutionReceipt,
    SandboxInvocationMandate,
    SandboxTeardownReceipt,
)


class SAllocDomainStatus(StrEnum):
    """Authoritative domain outcome statuses for S_ALLOC specialist calculations."""

    OK = "OK"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    INVALID_INPUT = "INVALID_INPUT"
    INFEASIBLE = "INFEASIBLE"
    UNSUPPORTED_MODEL = "UNSUPPORTED_MODEL"
    UNSUPPORTED_CONSTRAINT = "UNSUPPORTED_CONSTRAINT"
    SOLVER_FAILED = "SOLVER_FAILED"


def canonical_json_dumps(data: Any, exclude_fields: set[str] | None = None) -> bytes:
    """Serialize data into deterministic UTF-8 canonical JSON bytes.

    Rules enforced:
    - UTF-8 encoding
    - Sorted dictionary keys with minimal separators (',', ':')
    - NaN and Infinity are strictly rejected (allow_nan=False)
    - Normalized numeric representations (floats rounded to 6 decimal places)
    - Excludes self-referential digest and signature fields
    - Sets/frozensets are stably sorted as lists
    - Pydantic models are normalized via model_dump(mode='json')
    """
    excluded = exclude_fields or {
        "input_sha256",
        "output_sha256",
        "signature",
        "execution_receipt",
        "teardown_receipt",
    }

    def _normalize(val: Any) -> Any:
        if isinstance(val, BaseModel):
            val = val.model_dump(mode="json")
        if isinstance(val, dict):
            return {
                k: _normalize(v)
                for k, v in sorted(val.items(), key=lambda item: item[0])
                if k not in excluded
            }
        if isinstance(val, (list, tuple)):
            return [_normalize(item) for item in val]
        if isinstance(val, (set, frozenset)):
            return [_normalize(item) for item in sorted(val, key=lambda x: str(x))]
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"Non-finite float value '{val}' is rejected in canonical serialization."
                )
            return round(val, 6)
        if isinstance(val, datetime):
            val_utc = val if val.tzinfo is not None else val.replace(tzinfo=UTC)
            return val_utc.isoformat()
        return val

    normalized = _normalize(data)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_canonical_sha256(data: Any, exclude_fields: set[str] | None = None) -> str:
    """Compute deterministic SHA-256 digest over canonical JSON bytes."""
    raw_bytes = canonical_json_dumps(data, exclude_fields=exclude_fields)
    return hashlib.sha256(raw_bytes).hexdigest()


def parse_canonical_json_strictly(json_str_or_bytes: str | bytes) -> dict[str, Any]:
    """Parse JSON string or bytes, rejecting duplicate object keys and NaN/Infinity."""

    def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key detected in canonical JSON: '{key}'")
            result[key] = value
        return result

    raw_str = (
        json_str_or_bytes.decode("utf-8")
        if isinstance(json_str_or_bytes, bytes)
        else json_str_or_bytes
    )

    def _reject_constant(val: str) -> None:
        raise ValueError(f"Illegal non-finite constant in JSON: '{val}'")

    return json.loads(
        raw_str,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
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
    allocated_amount: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("allocated_amount", "spend"),
        serialization_alias="allocated_amount",
    )
    percentage_of_total: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        validation_alias=AliasChoices("percentage_of_total", "percentage"),
        serialization_alias="percentage_of_total",
    )
    role: str = ""
    primary_kpi: str = "mROI / incremental KPI"
    prior_roas: float | None = None
    target_roas_range: tuple[float, float] | None = None
    constraints: list[str] = Field(default_factory=list)

    def __init__(
        self,
        channel: str,
        allocated_amount: float | None = None,
        percentage_of_total: float | None = None,
        spend: float | None = None,
        percentage: float | None = None,
        role: str = "",
        primary_kpi: str = "mROI / incremental KPI",
        prior_roas: float | None = None,
        target_roas_range: tuple[float, float] | None = None,
        constraints: list[str] | None = None,
        **data: Any,
    ) -> None:
        amt = allocated_amount if allocated_amount is not None else spend
        pct = percentage_of_total if percentage_of_total is not None else percentage
        init_data: dict[str, Any] = {
            "channel": channel,
            "role": role,
            "primary_kpi": primary_kpi,
            "prior_roas": prior_roas,
            "target_roas_range": target_roas_range,
            "constraints": constraints or [],
            **data,
        }
        if amt is not None:
            init_data["allocated_amount"] = amt
        if pct is not None:
            init_data["percentage_of_total"] = pct
        super().__init__(**init_data)

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


class PerformanceContextReference(BaseModel):
    """Governed performance context reference and quality metadata passed to Strategy."""

    model_config = ConfigDict(extra="ignore")

    context_id: str
    tenant_id: str
    brand_id: str = "default"
    schema_version: str = "1.0"
    mapping_version: str = "1.0"
    source_coverage: dict[str, float] = Field(default_factory=dict)
    window_start: str | None = None
    window_end: str | None = None
    as_of_time: str | None = None
    metric_definitions: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    currency: str = "USD"
    attribution_assumptions: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    quality_flags: dict[str, Any] = Field(default_factory=dict)
    suppression_flags: dict[str, Any] = Field(default_factory=dict)
    freshness_flags: dict[str, Any] = Field(default_factory=dict)
    learning_reference: dict[str, Any] = Field(default_factory=dict)
    applicable_policy_version: str = "1.0"
    budget_version: str = "1.0"
    provenance_references: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    revalidation_conditions: list[str] = Field(default_factory=list)
    is_valid: bool = True
    blocking_reasons: list[str] = Field(default_factory=list)


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
    performance_context: PerformanceContextReference | None = None

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

        if self.performance_context:
            if self.performance_context.tenant_id != self.tenant_id:
                raise ValueError(
                    f"Tenant isolation breach in performance context: '{self.performance_context.tenant_id}' != '{self.tenant_id}'."
                )
            if self.performance_context.brand_id and self.brand_id and self.performance_context.brand_id != self.brand_id:
                raise ValueError(
                    f"Brand scope mismatch in performance context: '{self.performance_context.brand_id}' != '{self.brand_id}'."
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

        # 5. Governed performance context
        perf_ctx_raw = ctx.get("performance_context") or grant.cts_state.get("performance_context")
        perf_ctx: PerformanceContextReference | None = None
        if perf_ctx_raw:
            if isinstance(perf_ctx_raw, PerformanceContextReference):
                perf_ctx = perf_ctx_raw
            elif isinstance(perf_ctx_raw, dict):
                perf_ctx = PerformanceContextReference.model_validate(perf_ctx_raw)

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
            performance_context=perf_ctx,
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
                total_prop = round(sum(p.allocated_amount for p in self.channel_proposals), 2)
                if total_prop > round(self.strategy_plan.budget_ceiling, 2) + 0.01:
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

        raw_plan = (
            env.payload.get("strategy_plan")
            or env.payload.get("strategy_proposal")
            or getattr(env, "strategy_proposal", None)
        )
        if raw_plan:
            if isinstance(raw_plan, str):
                strategy_plan = OmnichannelStrategyPlan.model_validate_json(raw_plan)
            elif isinstance(raw_plan, dict):
                strategy_plan = OmnichannelStrategyPlan.model_validate(raw_plan)
            elif isinstance(raw_plan, OmnichannelStrategyPlan):
                strategy_plan = raw_plan
            else:
                raise ValueError(
                    f"strategy_plan in payload is not a valid plan type: {type(raw_plan)}"
                )

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


# ===========================================================================
# S_ALLOC Strict Specialist Execution Contracts (L6-01)
# ===========================================================================


class SAllocMandate(BaseModel):
    """Typed execution mandate for the S_ALLOC ephemeral specialist."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = "1.0"
    tenant_id: str = Field(..., min_length=1)
    brand_id: str = Field(default="default", min_length=1)
    task_id: str = Field(..., min_length=1)
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:12]}")
    stage_attempt_id: str = Field(default_factory=lambda: f"att-{uuid.uuid4().hex[:8]}")
    parent_grant_id: str = Field(..., min_length=1)
    parent_grant_version: str = Field(default="v1", min_length=1)
    parent_grant_hash: str = Field(default="", min_length=0)
    scenario_ids: list[str] = Field(default_factory=lambda: ["base"])
    worker_id: str = Field(default="W_STRAT", min_length=1)
    delegated_by: str = Field(default="W_STRAT", min_length=1)
    purpose: str = Field(default="media_and_budget_allocation", min_length=1)
    expires_at: datetime
    authorized_channels: list[str] = Field(..., min_length=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    currency_precision: int = Field(default=2, ge=0, le=4)
    budget_ceiling: float = Field(..., ge=0.0)
    cost_basis: str = Field(default="gross", min_length=1)
    allowed_operations: list[str] = Field(
        default_factory=lambda: [
            "model_media_mix",
            "optimize_budget",
            "simulate_funnel",
            "simulate_scenarios",
            "calculate_roas",
        ]
    )
    allowed_tools: list[str] = Field(
        default_factory=lambda: [
            "media_mix_modeler",
            "budget_allocator_tool",
            "funnel_simulator",
            "optimization_modeler",
            "allocation_solver",
            "diminishing_returns_model",
        ]
    )
    stop_rules: list[str] = Field(default_factory=list)
    token_quota: int = Field(default=4096, ge=1, le=128000)
    time_quota_seconds: int = Field(default=120, ge=1, le=600)
    cpu_cores: float = Field(default=1.0, ge=0.1, le=4.0)
    memory_mb: int = Field(default=1024, ge=128, le=8192)
    kpi_name: str | None = None
    kpi_unit: str | None = None
    time_horizon: str = Field(default="90_days", min_length=1)
    allocation_constraints: list[AllocationConstraint] = Field(default_factory=list)
    channel_parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    model_reference: str | dict[str, Any] = Field(default="planning_proxy")
    code_digest: str | None = None
    profile_reference: str = Field(default="w_strat.s_alloc.v1")
    policy_version: str = Field(default="v1")
    measurement_mode: Literal["planning_proxy", "validated_model_snapshot"] = "planning_proxy"
    missing_inputs: list[str] = Field(default_factory=list)
    algorithm_version: str = Field(default="1.0")
    uncertainty_method: str = Field(default="none")
    mroi_floor: float = Field(default=0.0, ge=0.0)
    input_sha256: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        curr = v.strip().upper()
        if len(curr) != 3 or not curr.isalpha():
            raise ValueError(f"Invalid currency code '{v}'; must be 3-letter ISO code.")
        return curr

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
    def validate_mandate_invariants(self) -> SAllocMandate:
        if not math.isfinite(self.budget_ceiling):
            raise ValueError(f"Budget ceiling must be a finite number: {self.budget_ceiling}")

        authorized_set = set(self.authorized_channels)
        seen_channels: set[str] = set()
        total_min_spend = 0.0
        total_min_share = 0.0

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

        # Validate channel parameters if provided
        for ch, params in self.channel_parameters.items():
            if ch not in authorized_set:
                raise ValueError(f"Channel parameters reference unauthorized channel '{ch}'")
            if not isinstance(params, dict):
                raise ValueError(f"Channel parameters for '{ch}' must be a dictionary.")
            if "initial_marginal_return" in params:
                imr = params["initial_marginal_return"]
                if not isinstance(imr, (int, float)) or not math.isfinite(imr) or imr < 0:
                    raise ValueError(f"initial_marginal_return for '{ch}' must be finite and >= 0")
            if "saturation_spend" in params:
                sat = params["saturation_spend"]
                if not isinstance(sat, (int, float)) or not math.isfinite(sat) or sat <= 0:
                    raise ValueError(f"saturation_spend for '{ch}' must be finite and > 0")

        return self

    def compute_input_digest(self) -> str:
        """Compute canonical SHA-256 digest over mandate excluding input_sha256."""
        return compute_canonical_sha256(self, exclude_fields={"input_sha256"})

    def validate_attenuation(
        self,
        parent_grant: TaskGrant,
        parent_directive: StrategyDirective | None = None,
    ) -> None:
        """Enforce strict authority attenuation against parent TaskGrant and StrategyDirective."""
        # 1. Expiry check
        current_time = datetime.now(UTC)
        grant_exp = (
            parent_grant.expires_at
            if parent_grant.expires_at.tzinfo is not None
            else parent_grant.expires_at.replace(tzinfo=UTC)
        )
        if current_time > grant_exp:
            raise PolicyViolationError(
                f"Parent TaskGrant '{parent_grant.task_id}' has expired at {grant_exp}."
            )

        mandate_exp = (
            self.expires_at
            if self.expires_at.tzinfo is not None
            else self.expires_at.replace(tzinfo=UTC)
        )
        if mandate_exp > grant_exp:
            raise PolicyViolationError(
                f"Mandate expires_at ({mandate_exp}) exceeds parent grant expires_at ({grant_exp})."
            )

        # 2. Identity binding
        if parent_grant.tenant_scope and self.tenant_id != parent_grant.tenant_scope.tenant_id:
            raise PolicyViolationError(
                f"Mandate tenant '{self.tenant_id}' does not match grant tenant '{parent_grant.tenant_scope.tenant_id}'."
            )
        if self.task_id != parent_grant.task_id:
            raise PolicyViolationError(
                f"Mandate task_id '{self.task_id}' does not match grant task_id '{parent_grant.task_id}'."
            )

        # 3. Budget attenuation
        max_allowed_budget = self.budget_ceiling
        if parent_directive is not None:
            max_allowed_budget = min(max_allowed_budget, parent_directive.budget_ceiling)
        if parent_grant.cts_state.get("budget_cap") is not None:
            with contextlib.suppress(ValueError, TypeError):
                max_allowed_budget = min(
                    max_allowed_budget, float(parent_grant.cts_state["budget_cap"])
                )
        elif parent_grant.budget_breakdown and "spend" in parent_grant.budget_breakdown:
            with contextlib.suppress(ValueError, TypeError):
                max_allowed_budget = min(
                    max_allowed_budget, float(parent_grant.budget_breakdown["spend"])
                )
        if self.budget_ceiling > max_allowed_budget + 1e-6:
            raise PolicyViolationError(
                f"Mandate budget_ceiling ({self.budget_ceiling}) exceeds authorized ceiling ({max_allowed_budget})."
            )

        # 4. Channel attenuation
        parent_allowed: set[str] = set()
        if parent_grant.tenant_scope and parent_grant.tenant_scope.allowed_channels:
            parent_allowed = {
                c.strip().lower() for c in parent_grant.tenant_scope.allowed_channels if c.strip()
            }
        if parent_directive is not None:
            dir_channels = set(parent_directive.authorized_channels)
            parent_allowed = parent_allowed.intersection(dir_channels) if parent_allowed else dir_channels

        if parent_allowed:
            mandate_channels = set(self.authorized_channels)
            unauthorized = mandate_channels - parent_allowed
            if unauthorized:
                raise PolicyViolationError(
                    f"Mandate contains unauthorized channels not permitted by parent grant: {sorted(unauthorized)}"
                )

        # 5. Quota attenuation
        if parent_grant.token_budget is not None and self.token_quota > parent_grant.token_budget:
            raise PolicyViolationError(
                f"Mandate token_quota ({self.token_quota}) exceeds grant token_budget ({parent_grant.token_budget})."
            )


class SAllocResult(BaseModel):
    """Typed sanitized calculation and diagnostic result from S_ALLOC."""

    model_config = ConfigDict(extra="forbid", strict=True)

    execution_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    stage_attempt_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    input_sha256: str = Field(..., min_length=64, max_length=64)
    status: SAllocDomainStatus = SAllocDomainStatus.OK
    scenario_allocations: dict[str, list[ChannelSpendProposal]] = Field(default_factory=dict)
    total_allocated: float = Field(default=0.0, ge=0.0)
    budget_residual: float = Field(default=0.0, ge=0.0)
    bound_residuals: dict[str, float] = Field(default_factory=dict)
    modeled_response: float = Field(default=0.0, ge=0.0)
    marginal_roas: dict[str, float] = Field(default_factory=dict)
    kpi_units: str = "modeled_units"
    funnel_metrics: dict[str, Any] | None = None
    measurement_mode: str = "planning_proxy"
    uncertainty_method: str = "none"
    uncertainty_intervals: dict[str, tuple[float, float]] | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    advisory_rationale: str | None = None
    output_sha256: str | None = None
    execution_receipt: SandboxExecutionReceipt | None = None
    teardown_receipt: SandboxTeardownReceipt | None = None

    @model_validator(mode="after")
    def validate_result_invariants(self) -> SAllocResult:
        if not math.isfinite(self.total_allocated):
            raise ValueError(f"total_allocated must be finite: {self.total_allocated}")
        if not math.isfinite(self.budget_residual):
            raise ValueError(f"budget_residual must be finite: {self.budget_residual}")
        if not math.isfinite(self.modeled_response):
            raise ValueError(f"modeled_response must be finite: {self.modeled_response}")
        for ch, mroi in self.marginal_roas.items():
            if not math.isfinite(mroi):
                raise ValueError(f"marginal_roas for '{ch}' must be finite: {mroi}")
        return self

    def compute_output_digest(self) -> str:
        """Compute canonical SHA-256 digest over result excluding self-referential fields."""
        return compute_canonical_sha256(
            self,
            exclude_fields={"output_sha256", "execution_receipt", "teardown_receipt"},
        )

    def verify_correlation(
        self,
        mandate: SAllocMandate | SandboxInvocationMandate | Any,
        *,
        require_receipts: bool = False,
    ) -> None:
        """Verify correlation identities, input digest, receipts, and domain bounds against authoritative mandate."""
        if self.execution_id != mandate.execution_id:
            raise ValueError(
                f"Result execution_id '{self.execution_id}' does not match mandate '{mandate.execution_id}'."
            )
        if self.task_id != mandate.task_id:
            raise ValueError(
                f"Result task_id '{self.task_id}' does not match mandate '{mandate.task_id}'."
            )
        if self.stage_attempt_id != mandate.stage_attempt_id:
            raise ValueError(
                f"Result stage_attempt_id '{self.stage_attempt_id}' does not match mandate '{mandate.stage_attempt_id}'."
            )
        if self.tenant_id != mandate.tenant_id:
            raise ValueError(
                f"Result tenant_id '{self.tenant_id}' does not match mandate '{mandate.tenant_id}'."
            )
        expected_input_hash = getattr(mandate, "input_sha256", None)
        if not expected_input_hash:
            if hasattr(mandate, "compute_input_digest"):
                expected_input_hash = mandate.compute_input_digest()
            elif hasattr(mandate, "payload"):
                expected_input_hash = compute_canonical_sha256(mandate.payload)
        if expected_input_hash and self.input_sha256 != expected_input_hash:
            raise ValueError(
                f"Result input_sha256 '{self.input_sha256}' does not match expected mandate digest '{expected_input_hash}'."
            )

        if self.status == SAllocDomainStatus.OK:
            if require_receipts:
                if self.execution_receipt is None or self.execution_receipt.exit_code != 0:
                    raise ValueError("SAllocResult with status OK must have a successful execution_receipt (exit_code 0).")
                if self.teardown_receipt is None or self.teardown_receipt.status not in ("CLEAN", "verified", "completed"):
                    raise ValueError("SAllocResult with status OK must have a verified teardown_receipt.")

            scenario_ids = getattr(mandate, "scenario_ids", None)
            if scenario_ids is None and hasattr(mandate, "payload"):
                scenario_ids = mandate.payload.get("scenarios")

            authorized_channels = getattr(mandate, "authorized_channels", None)
            if authorized_channels is None and hasattr(mandate, "payload"):
                authorized_channels = mandate.payload.get("channels")

            budget_ceiling = getattr(mandate, "budget_ceiling", None)
            if budget_ceiling is None and hasattr(mandate, "payload"):
                budget_ceiling = mandate.payload.get("target_budget") or mandate.payload.get("budget_ceiling")

            if self.scenario_allocations:
                if scenario_ids:
                    mandate_scenarios = set(scenario_ids)
                    result_scenarios = set(self.scenario_allocations.keys())
                    if result_scenarios != mandate_scenarios:
                        raise ValueError(
                            f"Result scenarios {sorted(result_scenarios)} do not match mandate scenarios {sorted(mandate_scenarios)}."
                        )
                if authorized_channels:
                    authorized = set(authorized_channels)
                    for sc_id, props in self.scenario_allocations.items():
                        sc_total = 0.0
                        for p in props:
                            if p.channel not in authorized:
                                raise ValueError(
                                    f"Scenario '{sc_id}' allocates to unauthorized channel '{p.channel}'. Authorized: {authorized_channels}"
                                )
                            amount = getattr(p, "allocated_amount", getattr(p, "spend", 0.0))
                            if amount < 0.0 or not math.isfinite(amount):
                                raise ValueError(
                                    f"Scenario '{sc_id}' channel '{p.channel}' has invalid amount: {amount}"
                                )
                            sc_total += amount
                        if budget_ceiling is not None and sc_total > budget_ceiling + 0.01:
                            raise ValueError(
                                f"Scenario '{sc_id}' total ({sc_total}) exceeds ceiling ({budget_ceiling})."
                            )

            if budget_ceiling is not None and self.total_allocated + self.budget_residual > budget_ceiling + 0.01:
                raise ValueError(
                    f"Total allocated ({self.total_allocated}) + residual ({self.budget_residual}) "
                    f"exceeds mandate budget ceiling ({budget_ceiling})."
                )

