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


class Directive(BaseModel):
    """An owner-issued objective, scope, budget, and risk directive."""

    directive_id: str
    tenant_id: str
    objective: str
    budget_cap: float = Field(ge=0)
    risk_ceiling: RiskLevel = RiskLevel.LOW
    scope: TenantScope
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyDecision(BaseModel):
    """The outcome of evaluating a requested action against policy."""

    allowed: bool
    reason: str
    risk_level: RiskLevel
    constraints: dict[str, str] = Field(default_factory=dict)