"""Enforces caller identity, delegation, tenant scope, risk, and attenuation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.exceptions import AuthorizationError
from app.schemas.governance import AutonomyTier, DecisionOutcome, RiskLevel, TenantScope
from app.security.scope_evaluator import ScopeEvaluator

if TYPE_CHECKING:
    from app.security.cryptographic_validator import CryptographicValidator


@dataclass(frozen=True)
class CallerIdentity:
    """The authenticated identity of a caller crossing the authorization boundary."""

    subject: str
    tenant_scope: TenantScope
    risk_ceiling: RiskLevel
    delegation_chain: tuple[str, ...] = ("root",)
    autonomy_tier: AutonomyTier = AutonomyTier.TIER_3_HIGH_RISK_GATED
    allowed_capabilities: frozenset[str] = frozenset({"*"})
    token: str | None = None
    signature: str | None = None
    expires_at: datetime | None = None
    max_budget: float | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    """The deterministic result of evaluating a caller against the boundary."""

    outcome: DecisionOutcome
    allowed: bool
    reason: str
    reason_code: str


class AuthorizationBoundary:
    """The single point where caller identity is checked against a request."""

    def __init__(
        self,
        scope_evaluator: ScopeEvaluator | None = None,
        crypto_validator: CryptographicValidator | None = None,
    ) -> None:
        self._scope_evaluator = scope_evaluator or ScopeEvaluator()
        self._crypto_validator = crypto_validator

    def evaluate(
        self,
        caller: CallerIdentity,
        *,
        requested_scope: TenantScope,
        requested_risk: RiskLevel,
        requested_capability: str | None = None,
        requested_autonomy: AutonomyTier | None = None,
        requested_budget: float | None = None,
        delegation_parent: str | None = None,
        verification_payload: bytes | None = None,
        requires_escalation: bool = False,
    ) -> AuthorizationDecision:
        """Return a deterministic Allow, Deny, or Escalate decision. Missing/invalid fails closed."""
        if not caller.subject or not caller.subject.strip():
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason="Caller identity subject cannot be empty.",
                reason_code="INVALID_SUBJECT",
            )

        if not caller.delegation_chain:
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Caller '{caller.subject}' has an empty delegation chain.",
                reason_code="EMPTY_DELEGATION_CHAIN",
            )

        if delegation_parent is not None and delegation_parent not in caller.delegation_chain:
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=(
                    f"Caller '{caller.subject}' delegation chain {caller.delegation_chain} "
                    f"does not include required delegation parent '{delegation_parent}'."
                ),
                reason_code="DELEGATION_PARENT_MISSING",
            )

        if caller.token is not None and not caller.token.strip():
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Caller '{caller.subject}' provided an empty authorization token.",
                reason_code="INVALID_TOKEN",
            )

        if caller.expires_at is not None and datetime.now(UTC) > caller.expires_at:
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Caller '{caller.subject}' authorization has expired at {caller.expires_at.isoformat()}.",
                reason_code="EXPIRED_AUTHORIZATION",
            )

        if caller.signature is not None and verification_payload is not None:
            if self._crypto_validator is None:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    allowed=False,
                    reason="Cannot verify caller signature without configured CryptographicValidator.",
                    reason_code="CRYPTO_VALIDATOR_MISSING",
                )
            if not self._crypto_validator.verify(verification_payload, caller.signature):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    allowed=False,
                    reason=f"Cryptographic signature verification failed for caller '{caller.subject}'.",
                    reason_code="SIGNATURE_VERIFICATION_FAILED",
                )

        if not self._scope_evaluator.evaluate(requested_scope, caller.tenant_scope):
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Caller '{caller.subject}' has no delegated authority over the requested scope.",
                reason_code="SCOPE_EXCEEDED",
            )

        if requested_risk.exceeds(caller.risk_ceiling):
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=(
                    f"Caller '{caller.subject}' risk ceiling '{caller.risk_ceiling.value}' does not "
                    f"permit requested risk '{requested_risk.value}'."
                ),
                reason_code="RISK_EXCEEDED",
            )

        if requested_autonomy is not None and requested_autonomy.exceeds(caller.autonomy_tier):
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=(
                    f"Caller '{caller.subject}' autonomy tier '{caller.autonomy_tier.value}' does not "
                    f"permit requested autonomy '{requested_autonomy.value}'."
                ),
                reason_code="AUTONOMY_EXCEEDED",
            )

        if (
            requested_capability is not None
            and "*" not in caller.allowed_capabilities
            and requested_capability not in caller.allowed_capabilities
        ):
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Caller '{caller.subject}' lacks capability '{requested_capability}'.",
                reason_code="CAPABILITY_MISSING",
            )

        if requested_budget is not None and caller.max_budget is not None and requested_budget > caller.max_budget:
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                allowed=False,
                reason=f"Requested budget {requested_budget} exceeds caller '{caller.subject}' budget ceiling {caller.max_budget}.",
                reason_code="BUDGET_EXCEEDED",
            )

        if requires_escalation:
            return AuthorizationDecision(
                outcome=DecisionOutcome.ESCALATE,
                allowed=False,
                reason=f"Requested action by '{caller.subject}' requires escalation to higher authority; execution held.",
                reason_code="ESCALATE_REQUIRED",
            )

        return AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            allowed=True,
            reason="Caller authorized within delegated scope, risk ceiling, and policy boundaries.",
            reason_code="ALLOW",
        )

    def authorize(
        self,
        caller: CallerIdentity,
        *,
        requested_scope: TenantScope,
        requested_risk: RiskLevel,
        requested_capability: str | None = None,
        requested_autonomy: AutonomyTier | None = None,
        requested_budget: float | None = None,
        delegation_parent: str | None = None,
        verification_payload: bytes | None = None,
        requires_escalation: bool = False,
    ) -> None:
        """Raise ``AuthorizationError`` unless ``caller`` may act at the requested level."""
        decision = self.evaluate(
            caller,
            requested_scope=requested_scope,
            requested_risk=requested_risk,
            requested_capability=requested_capability,
            requested_autonomy=requested_autonomy,
            requested_budget=requested_budget,
            delegation_parent=delegation_parent,
            verification_payload=verification_payload,
            requires_escalation=requires_escalation,
        )
        if not decision.allowed:
            raise AuthorizationError(decision.reason)

    def authorize_sandbox_action(
        self,
        caller: CallerIdentity,
        *,
        lease: Any | None = None,
        target_resource: str,
        is_sandbox_origin: bool = False,
    ) -> None:
        """Enforce sandbox execution boundaries and Model-A security invariants.

        1. Require valid execution lease for sandbox provisioning/execution.
        2. Block any caller originating from inside a sandbox or presenting sandbox credentials
           from directly accessing enterprise database, RAG vector stores, Intelligence Engine
           internals, production CMS/Ads/Social actuation, or host services.
        """
        if is_sandbox_origin or "sandbox" in caller.subject.lower():
            prohibited_resources = (
                "database",
                "persistence",
                "rag",
                "vector_store",
                "intelligence_engine_internal",
                "cms_production",
                "ads_production",
                "social_production",
                "host_fs",
                "cloud_metadata",
            )
            target_norm = target_resource.strip().lower()
            for prohibited in prohibited_resources:
                if prohibited in target_norm:
                    raise AuthorizationError(
                        f"Model-A Security Violation: Sandbox-originating caller '{caller.subject}' is "
                        f"strictly forbidden from accessing protected resource '{target_resource}'."
                    )

        if lease is not None:
            if hasattr(lease, "is_expired") and lease.is_expired():
                raise AuthorizationError(
                    f"Sandbox authorization failed: Execution lease '{getattr(lease, 'lease_id', 'unknown')}' has expired."
                )