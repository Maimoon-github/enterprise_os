"""Enforces caller identity, delegation, tenant scope, risk, and attenuation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.exceptions import AuthorizationError
from app.schemas.governance import AutonomyTier, RiskLevel, TenantScope
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


class AuthorizationBoundary:
    """The single point where caller identity is checked against a request."""

    def __init__(
        self,
        scope_evaluator: ScopeEvaluator | None = None,
        crypto_validator: CryptographicValidator | None = None,
    ) -> None:
        self._scope_evaluator = scope_evaluator or ScopeEvaluator()
        self._crypto_validator = crypto_validator

    def authorize(
        self,
        caller: CallerIdentity,
        *,
        requested_scope: TenantScope,
        requested_risk: RiskLevel,
        requested_capability: str | None = None,
        requested_autonomy: AutonomyTier | None = None,
        delegation_parent: str | None = None,
        verification_payload: bytes | None = None,
    ) -> None:
        """Raise ``AuthorizationError`` unless ``caller`` may act at the requested level.

        Enforces monotonic attenuation:
        1. Caller identity must be valid and authenticated.
        2. Delegation chain must be intact and rooted in authority.
        3. Signatures/tokens must be verified when cryptographic proof is supplied.
        4. Requested scope must be a subset of the caller's delegated scope.
        5. Requested risk must not exceed caller's risk ceiling.
        6. Requested autonomy tier must not exceed caller's autonomy tier.
        7. Requested capability must be in caller's allowed capabilities.
        """

        if not caller.subject or not caller.subject.strip():
            raise AuthorizationError("Caller identity subject cannot be empty.")

        if not caller.delegation_chain:
            raise AuthorizationError(f"Caller '{caller.subject}' has an empty delegation chain.")

        if delegation_parent is not None and delegation_parent not in caller.delegation_chain:
            raise AuthorizationError(
                f"Caller '{caller.subject}' delegation chain {caller.delegation_chain} "
                f"does not include required delegation parent '{delegation_parent}'."
            )

        if caller.token is not None and not caller.token.strip():
            raise AuthorizationError(f"Caller '{caller.subject}' provided an empty authorization token.")

        if caller.signature is not None and verification_payload is not None:
            if self._crypto_validator is None:
                raise AuthorizationError(
                    "Cannot verify caller signature without configured CryptographicValidator."
                )
            if not self._crypto_validator.verify(verification_payload, caller.signature):
                raise AuthorizationError(
                    f"Cryptographic signature verification failed for caller '{caller.subject}'."
                )

        if not self._scope_evaluator.evaluate(requested_scope, caller.tenant_scope):
            raise AuthorizationError(
                f"Caller '{caller.subject}' has no delegated authority over the requested scope."
            )

        if requested_risk.exceeds(caller.risk_ceiling):
            raise AuthorizationError(
                f"Caller '{caller.subject}' risk ceiling '{caller.risk_ceiling.value}' does not "
                f"permit requested risk '{requested_risk.value}'."
            )

        if requested_autonomy is not None and requested_autonomy.exceeds(caller.autonomy_tier):
            raise AuthorizationError(
                f"Caller '{caller.subject}' autonomy tier '{caller.autonomy_tier.value}' does not "
                f"permit requested autonomy '{requested_autonomy.value}'."
            )

        if (
            requested_capability is not None
            and "*" not in caller.allowed_capabilities
            and requested_capability not in caller.allowed_capabilities
        ):
            raise AuthorizationError(
                f"Caller '{caller.subject}' lacks capability '{requested_capability}'."
            )

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