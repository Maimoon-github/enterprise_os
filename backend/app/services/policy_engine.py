"""Produces and validates machine-readable policy and compliance envelopes."""

from __future__ import annotations

from typing import TypedDict

from app.schemas.governance import Directive, RiskLevel, TenantScope


class PolicyEnvelope(TypedDict):
    """A structural, machine-readable description of a policy decision input."""

    directive_id: str
    tenant_id: str
    brand_ids: list[str]
    allowed_channels: list[str]
    risk_level: str
    budget_cap: float


class PolicyEngine:
    """Builds and structurally validates policy envelopes."""

    _REQUIRED_KEYS = frozenset(
        {"directive_id", "tenant_id", "brand_ids", "allowed_channels", "risk_level", "budget_cap"}
    )

    def build_envelope(
        self,
        directive: Directive,
        scope: TenantScope,
        risk_level: RiskLevel,
    ) -> PolicyEnvelope:
        """Assemble a policy envelope from a directive and a requested scope."""

        return PolicyEnvelope(
            directive_id=directive.directive_id,
            tenant_id=scope.tenant_id,
            brand_ids=list(scope.brand_ids),
            allowed_channels=list(scope.allowed_channels),
            risk_level=risk_level.value,
            budget_cap=directive.budget_cap,
        )

    def validate_envelope(self, envelope: PolicyEnvelope) -> bool:
        """Return True if ``envelope`` contains all required, well-typed fields."""

        if not self._REQUIRED_KEYS.issubset(envelope.keys()):
            return False
        if envelope["budget_cap"] < 0:
            return False
        return envelope["risk_level"] in {level.value for level in RiskLevel}