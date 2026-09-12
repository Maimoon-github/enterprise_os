"""Produces and validates machine-readable policy and compliance envelopes."""

from __future__ import annotations

from typing import Any, TypedDict
import uuid

from app.schemas.governance import (
    AutonomyTier,
    Directive,
    RiskLevel,
    TenantScope,
    VersionedPolicyEnvelope,
)


class PolicyEnvelope(TypedDict, total=False):
    """A structural, machine-readable description of a policy decision input."""

    policy_id: str
    version: str
    directive_id: str
    tenant_id: str
    brand_ids: list[str]
    allowed_channels: list[str]
    risk_level: str
    budget_cap: float
    autonomy_tier: str
    spending_limit: float
    permitted_claims: list[str]
    prohibited_actions: list[str]
    legal_rules: list[str]
    escalation_thresholds: dict[str, float]
    mandatory_approval_conditions: list[str]


class PolicyEngine:
    """Builds, versions, and structurally validates machine-readable policy envelopes."""

    _REQUIRED_KEYS = frozenset(
        {"directive_id", "tenant_id", "brand_ids", "allowed_channels", "risk_level", "budget_cap"}
    )

    def __init__(self) -> None:
        self._envelopes: dict[tuple[str, str], VersionedPolicyEnvelope] = {}

    def build_envelope(
        self,
        directive: Directive,
        scope: TenantScope,
        risk_level: RiskLevel,
        autonomy_tier: AutonomyTier | None = None,
    ) -> PolicyEnvelope:
        """Assemble a policy envelope from a directive and a requested scope."""

        return PolicyEnvelope(
            policy_id=f"pol-{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            directive_id=directive.directive_id,
            tenant_id=scope.tenant_id,
            brand_ids=list(scope.brand_ids),
            allowed_channels=list(scope.allowed_channels),
            risk_level=risk_level.value,
            budget_cap=directive.budget_cap,
            autonomy_tier=(autonomy_tier or directive.autonomy_limit).value,
            spending_limit=directive.budget_cap,
            permitted_claims=list(directive.permitted_claims),
            prohibited_actions=list(directive.prohibited_actions),
            legal_rules=list(directive.operational_constraints),
            escalation_thresholds={"budget_utilization": 0.85, "risk_escalation_rank": 2.0},
            mandatory_approval_conditions=[
                "external_dispatch",
                "spend_above_budget",
                "high_risk_claim",
            ],
        )

    def build_versioned_envelope(
        self,
        directive: Directive,
        scope: TenantScope,
        *,
        version: str = "1.0.0",
        risk_level: RiskLevel | None = None,
        autonomy_tier: AutonomyTier | None = None,
        legal_rules: list[str] | None = None,
        escalation_thresholds: dict[str, float] | None = None,
        mandatory_approval_conditions: list[str] | None = None,
    ) -> VersionedPolicyEnvelope:
        """Construct, validate, and register a typed VersionedPolicyEnvelope."""

        envelope = VersionedPolicyEnvelope(
            policy_id=f"pol-{uuid.uuid4().hex[:8]}",
            version=version,
            directive_id=directive.directive_id,
            tenant_id=scope.tenant_id,
            brand_ids=list(scope.brand_ids),
            allowed_channels=list(scope.allowed_channels),
            risk_ceiling=risk_level or directive.risk_ceiling,
            autonomy_tier=autonomy_tier or directive.autonomy_limit,
            spending_limit=directive.budget_cap,
            permitted_claims=list(directive.permitted_claims),
            prohibited_actions=list(directive.prohibited_actions),
            legal_rules=legal_rules if legal_rules is not None else list(directive.operational_constraints),
            escalation_thresholds=escalation_thresholds or {"budget_utilization": 0.85},
            mandatory_approval_conditions=mandatory_approval_conditions
            or ["external_dispatch", "high_risk_claim"],
        )
        self.register_envelope(envelope)
        return envelope

    def register_envelope(self, envelope: VersionedPolicyEnvelope) -> None:
        """Register a versioned policy envelope into the policy engine."""

        self._envelopes[(envelope.tenant_id, envelope.version)] = envelope

    def get_envelope(self, tenant_id: str, version: str = "1.0.0") -> VersionedPolicyEnvelope | None:
        """Retrieve a registered versioned policy envelope."""

        return self._envelopes.get((tenant_id, version))

    def list_envelopes(self, tenant_id: str | None = None) -> list[VersionedPolicyEnvelope]:
        """List all versioned policy envelopes, optionally filtered by tenant."""

        if tenant_id is not None:
            return [env for (t_id, _), env in self._envelopes.items() if t_id == tenant_id]
        return list(self._envelopes.values())

    def validate_envelope(self, envelope: PolicyEnvelope | dict[str, Any]) -> bool:
        """Return True if ``envelope`` contains all required, well-typed fields."""

        if not self._REQUIRED_KEYS.issubset(envelope.keys()):
            return False
        if envelope["budget_cap"] < 0:
            return False
        if envelope["risk_level"] not in {level.value for level in RiskLevel}:
            return False
        if "autonomy_tier" in envelope and envelope["autonomy_tier"] not in {
            t.value for t in AutonomyTier
        }:
            return False
        return True

    def is_claim_permitted(self, claim: str, envelope: VersionedPolicyEnvelope | PolicyEnvelope) -> bool:
        """Verify whether a marketing/product claim is permitted by policy."""

        permitted = (
            envelope.permitted_claims
            if isinstance(envelope, VersionedPolicyEnvelope)
            else envelope.get("permitted_claims", [])
        )
        if not permitted:
            return True
        return any(p.lower() in claim.lower() or claim.lower() in p.lower() for p in permitted)

    def is_action_prohibited(self, action: str, envelope: VersionedPolicyEnvelope | PolicyEnvelope) -> bool:
        """Check whether an action is strictly prohibited by policy."""

        prohibited = (
            envelope.prohibited_actions
            if isinstance(envelope, VersionedPolicyEnvelope)
            else envelope.get("prohibited_actions", [])
        )
        return action in prohibited