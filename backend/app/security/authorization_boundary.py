"""Enforces caller identity, delegation, tenant scope, risk, and attenuation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthzDecision:
    allowed: bool
    reason: str | None = None


class AuthorizationBoundary:
    def check(
        self,
        caller_tenant: str,
        target_tenant: str,
        scopes: set[str],
        required: set[str],
    ) -> AuthzDecision:
        if caller_tenant != target_tenant:
            return AuthzDecision(False, "tenant mismatch")
        missing = required - scopes
        if missing:
            return AuthzDecision(False, f"missing scopes: {sorted(missing)}")
        return AuthzDecision(True)
