"""Enforces caller identity, delegation, tenant scope, risk, and attenuation."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AuthorizationError
from app.schemas.governance import RiskLevel, TenantScope
from app.security.scope_evaluator import ScopeEvaluator


@dataclass(frozen=True)
class CallerIdentity:
    """The authenticated identity of a caller crossing the authorization boundary."""

    subject: str
    tenant_scope: TenantScope
    risk_ceiling: RiskLevel


class AuthorizationBoundary:
    """The single point where caller identity is checked against a request."""

    def __init__(self, scope_evaluator: ScopeEvaluator | None = None) -> None:
        self._scope_evaluator = scope_evaluator or ScopeEvaluator()

    def authorize(
        self,
        caller: CallerIdentity,
        *,
        requested_scope: TenantScope,
        requested_risk: RiskLevel,
    ) -> None:
        """Raise ``AuthorizationError`` unless ``caller`` may act at the requested level.

        Enforces two invariants: the requested scope must be a subset of the
        caller's delegated scope, and the requested risk must not exceed the
        caller's risk ceiling (monotonic attenuation).
        """

        if not self._scope_evaluator.evaluate(requested_scope, caller.tenant_scope):
            raise AuthorizationError(
                f"Caller '{caller.subject}' has no delegated authority over the requested scope."
            )
        if requested_risk.exceeds(caller.risk_ceiling):
            raise AuthorizationError(
                f"Caller '{caller.subject}' risk ceiling '{caller.risk_ceiling.value}' does not "
                f"permit requested risk '{requested_risk.value}'."
            )