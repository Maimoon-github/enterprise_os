"""Directives, policy envelopes, tenant scopes, budgets, and risk data."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Budget(BaseModel):
    currency: str = "USD"
    amount: float = Field(ge=0.0)


class RiskEnvelope(BaseModel):
    max_spend: float = Field(ge=0.0)
    max_risk_score: float = Field(ge=0.0, le=1.0)


class Directive(BaseModel):
    directive_id: str
    tenant_id: str
    objective: str
    scopes: list[str] = Field(default_factory=list)
    budget: Budget
    risk: RiskEnvelope


class PolicyEnvelope(BaseModel):
    policy_id: str
    directive_id: str
    tenant_id: str
    scopes: list[str]
    budget: Budget
    risk: RiskEnvelope
