"""Applies policy decisions before delegation and execution.

Enforces monotonic attenuation: a delegated grant may never carry a risk
level or scope broader than the directive that authorized it.
"""

from __future__ import annotations

from app.schemas.governance import (
    AutonomyTier,
    Directive,
    PolicyDecision,
    RiskLevel,
    TenantScope,
)
from app.services.policy_engine import PolicyEngine


class PolicyEvaluator:
    """Evaluates a proposed delegation against its parent directive."""

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self._policy_engine = policy_engine or PolicyEngine()

    def evaluate_delegation(
        self,
        directive: Directive,
        requested_scope: TenantScope,
        requested_risk: RiskLevel,
        requested_autonomy: AutonomyTier | None = None,
        requested_claim: str | None = None,
        requested_action: str | None = None,
    ) -> PolicyDecision:
        """Return whether a worker delegation is permitted under ``directive``."""

        if not requested_scope.is_subset_of(directive.scope):
            return PolicyDecision(
                allowed=False,
                reason="Requested scope exceeds directive-delegated tenant scope.",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        if requested_risk.exceeds(directive.risk_ceiling):
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Requested risk '{requested_risk.value}' exceeds directive "
                    f"ceiling '{directive.risk_ceiling.value}'."
                ),
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        if requested_autonomy and requested_autonomy.exceeds(directive.autonomy_limit):
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Requested autonomy '{requested_autonomy.value}' exceeds directive "
                    f"limit '{directive.autonomy_limit.value}'."
                ),
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        envelope = self._policy_engine.build_envelope(
            directive, requested_scope, requested_risk, requested_autonomy
        )
        if not self._policy_engine.validate_envelope(envelope):
            return PolicyDecision(
                allowed=False,
                reason="Policy envelope failed structural validation.",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        if requested_action and self._policy_engine.is_action_prohibited(requested_action, envelope):
            return PolicyDecision(
                allowed=False,
                reason=f"Requested action '{requested_action}' is prohibited by policy.",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        if requested_claim and not self._policy_engine.is_claim_permitted(requested_claim, envelope):
            return PolicyDecision(
                allowed=False,
                reason=f"Requested claim '{requested_claim}' is not permitted by policy boundaries.",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
            )

        return PolicyDecision(
            allowed=True,
            reason="Delegation within directive scope, risk ceiling, and policy boundaries.",
            risk_level=requested_risk,
            autonomy_tier=requested_autonomy,
        )