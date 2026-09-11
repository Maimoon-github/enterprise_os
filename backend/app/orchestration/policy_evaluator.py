"""Applies policy decisions before delegation and execution.

Enforces monotonic attenuation: a delegated grant may never carry a risk
level or scope broader than the directive that authorized it.
"""

from __future__ import annotations

from app.schemas.governance import Directive, PolicyDecision, RiskLevel, TenantScope
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
    ) -> PolicyDecision:
        """Return whether a worker delegation is permitted under ``directive``."""

        if not requested_scope.is_subset_of(directive.scope):
            return PolicyDecision(
                allowed=False,
                reason="Requested scope exceeds directive-delegated tenant scope.",
                risk_level=requested_risk,
            )

        if requested_risk.exceeds(directive.risk_ceiling):
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Requested risk '{requested_risk.value}' exceeds directive "
                    f"ceiling '{directive.risk_ceiling.value}'."
                ),
                risk_level=requested_risk,
            )

        envelope = self._policy_engine.build_envelope(directive, requested_scope, requested_risk)
        if not self._policy_engine.validate_envelope(envelope):
            return PolicyDecision(
                allowed=False,
                reason="Policy envelope failed structural validation.",
                risk_level=requested_risk,
            )

        return PolicyDecision(
            allowed=True,
            reason="Delegation within directive scope and risk ceiling.",
            risk_level=requested_risk,
        )