"""Foundational governance contracts shared across the backend.

This module defines the enums and directive/policy contracts that every
other schema, service, and orchestration module builds on, so worker roles,
risk levels, and tenant scope are defined exactly once.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WorkerRole(StrEnum):
    """The seven bounded worker agents with no direct data-store access."""

    DEVELOPMENT = "W_DEV"
    STRATEGY = "W_STRAT"
    CREATIVE_CONTENT = "W_CREAT"
    PRODUCT_EVIDENCE = "W_PROD"
    COMPETITOR_INTEL = "W_COMP"
    CUSTOMER_VOICE = "W_VOICE"
    LEARNING_PERFORMANCE = "W_LEARN"


class RiskLevel(StrEnum):
    """Ordered risk ceiling used for monotonic policy attenuation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Numeric ordering used for monotonic risk-ceiling comparisons."""

        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    def exceeds(self, ceiling: RiskLevel) -> bool:
        """Return True if this risk level is strictly above ``ceiling``."""

        return self.rank > ceiling.rank


class TenantScope(BaseModel):
    """Delegated tenant/brand/channel authority granted to a directive or task."""

    tenant_id: str
    brand_ids: list[str] = Field(default_factory=list)
    allowed_channels: list[str] = Field(default_factory=list)

    def is_subset_of(self, parent: TenantScope) -> bool:
        """Return True if this scope requests no more than ``parent`` grants."""

        if self.tenant_id != parent.tenant_id:
            return False
        if not set(self.brand_ids).issubset(set(parent.brand_ids)):
            return False
        return set(self.allowed_channels).issubset(set(parent.allowed_channels))


class AutonomyTier(StrEnum):
    """Autonomy levels for agentic execution."""

    TIER_0_INFORMATIONAL = "tier_0_informational"
    TIER_1_ASSISTED = "tier_1_assisted"
    TIER_2_AUTONOMOUS = "tier_2_autonomous"
    TIER_3_HIGH_RISK_GATED = "tier_3_high_risk_gated"

    @property
    def rank(self) -> int:
        """Numeric ordering for monotonic autonomy comparisons."""

        return {
            "tier_0_informational": 0,
            "tier_1_assisted": 1,
            "tier_2_autonomous": 2,
            "tier_3_high_risk_gated": 3,
        }[self.value]

    def exceeds(self, ceiling: AutonomyTier) -> bool:
        """Return True if this autonomy tier is strictly above ``ceiling``."""

        return self.rank > ceiling.rank


class Directive(BaseModel):
    """An owner-issued objective, scope, budget, and risk directive."""

    directive_id: str
    tenant_id: str
    objective: str
    budget_cap: float = Field(ge=0)
    risk_ceiling: RiskLevel = RiskLevel.LOW
    scope: TenantScope
    autonomy_limit: AutonomyTier = AutonomyTier.TIER_2_AUTONOMOUS
    operational_constraints: list[str] = Field(default_factory=list)
    permitted_claims: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    is_approved: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VersionedPolicyEnvelope(BaseModel):
    """Machine-readable, versioned policy envelope for governance enforcement."""

    policy_id: str
    version: str = "1.0.0"
    tenant_id: str
    directive_id: str
    brand_ids: list[str] = Field(default_factory=list)
    allowed_channels: list[str] = Field(default_factory=list)
    risk_ceiling: RiskLevel = RiskLevel.MEDIUM
    autonomy_tier: AutonomyTier = AutonomyTier.TIER_2_AUTONOMOUS
    spending_limit: float = Field(ge=0)
    permitted_claims: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    legal_rules: list[str] = Field(default_factory=list)
    escalation_thresholds: dict[str, float] = Field(default_factory=dict)
    mandatory_approval_conditions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyDecision(BaseModel):
    """The outcome of evaluating a requested action against policy."""

    allowed: bool
    reason: str
    risk_level: RiskLevel
    autonomy_tier: AutonomyTier | None = None
    constraints: dict[str, str] = Field(default_factory=dict)