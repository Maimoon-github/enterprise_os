"""Applies policy decisions before delegation and execution.

Enforces monotonic attenuation: a delegated grant may never carry a risk
level or scope broader than the directive that authorized it.
"""

from __future__ import annotations

import hashlib
import json

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
        requires_review: bool = False,
    ) -> PolicyDecision:
        """Return whether a worker delegation is permitted under ``directive``."""

        if not requested_scope.is_subset_of(directive.scope):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason="Requested scope exceeds directive-delegated tenant scope.",
                reason_code="SCOPE_EXCEEDED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        if requested_risk.exceeds(directive.risk_ceiling):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason=(
                    f"Requested risk '{requested_risk.value}' exceeds directive "
                    f"ceiling '{directive.risk_ceiling.value}'."
                ),
                reason_code="RISK_EXCEEDED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        if requested_autonomy and requested_autonomy.exceeds(directive.autonomy_limit):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason=(
                    f"Requested autonomy '{requested_autonomy.value}' exceeds directive "
                    f"limit '{directive.autonomy_limit.value}'."
                ),
                reason_code="AUTONOMY_EXCEEDED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        envelope = self._policy_engine.build_envelope(
            directive, requested_scope, requested_risk, requested_autonomy
        )
        if not self._policy_engine.validate_envelope(envelope):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason="Policy envelope failed structural validation.",
                reason_code="POLICY_INVALID",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        if requested_action and self._policy_engine.is_action_prohibited(requested_action, envelope):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason=f"Requested action '{requested_action}' is prohibited by policy.",
                reason_code="ACTION_PROHIBITED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        if requested_claim and not self._policy_engine.is_claim_permitted(requested_claim, envelope):
            return PolicyDecision(
                decision="deny",
                allowed=False,
                reason=f"Requested claim '{requested_claim}' is not permitted by policy boundaries.",
                reason_code="CLAIM_NOT_PERMITTED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                scope=requested_scope,
            )

        envelope_hash = hashlib.sha256(
            json.dumps(envelope, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        action_hash = (
            hashlib.sha256(requested_action.encode("utf-8")).hexdigest()
            if requested_action
            else None
        )

        if requires_review:
            return PolicyDecision(
                decision="review",
                allowed=False,
                reason="Delegation within bounds but requires human review.",
                reason_code="REVIEW_REQUIRED",
                risk_level=requested_risk,
                autonomy_tier=requested_autonomy,
                tenant_id=requested_scope.tenant_id,
                policy_id=envelope.get("policy_id"),
                policy_version=envelope.get("version"),
                policy_hash=envelope_hash,
                action_hash=action_hash,
                scope=requested_scope,
                spending_limit=directive.budget_cap,
            )

        return PolicyDecision(
            decision="allow",
            allowed=True,
            reason="Delegation within directive scope, risk ceiling, and policy boundaries.",
            reason_code="ALLOW",
            risk_level=requested_risk,
            autonomy_tier=requested_autonomy,
            tenant_id=requested_scope.tenant_id,
            policy_id=envelope.get("policy_id"),
            policy_version=envelope.get("version"),
            policy_hash=envelope_hash,
            action_hash=action_hash,
            scope=requested_scope,
            spending_limit=directive.budget_cap,
        )