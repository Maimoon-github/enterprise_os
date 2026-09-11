"""Verifies policy decisions and monotonic attenuation."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity


def test_delegation_within_scope_and_risk_is_allowed(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()

    decision = evaluator.evaluate_delegation(
        sample_directive, sample_directive.scope, RiskLevel.LOW
    )

    assert decision.allowed is True


def test_delegation_exceeding_risk_ceiling_is_denied(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()

    decision = evaluator.evaluate_delegation(
        sample_directive, sample_directive.scope, RiskLevel.CRITICAL
    )

    assert decision.allowed is False
    assert "exceeds" in decision.reason


def test_delegation_outside_scope_is_denied(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()
    broader_scope = TenantScope(
        tenant_id=sample_directive.tenant_id,
        brand_ids=[*sample_directive.scope.brand_ids, "unauthorized-brand"],
        allowed_channels=sample_directive.scope.allowed_channels,
    )

    decision = evaluator.evaluate_delegation(sample_directive, broader_scope, RiskLevel.LOW)

    assert decision.allowed is False
    assert "scope" in decision.reason.lower()


def test_risk_level_rank_is_monotonic() -> None:
    assert RiskLevel.LOW.rank < RiskLevel.MEDIUM.rank
    assert RiskLevel.MEDIUM.rank < RiskLevel.HIGH.rank
    assert RiskLevel.HIGH.rank < RiskLevel.CRITICAL.rank
    assert RiskLevel.HIGH.exceeds(RiskLevel.MEDIUM)
    assert not RiskLevel.MEDIUM.exceeds(RiskLevel.HIGH)


def test_authorization_boundary_allows_caller_within_delegation(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.HIGH
    )

    boundary.authorize(caller, requested_scope=sample_tenant_scope, requested_risk=RiskLevel.LOW)


def test_authorization_boundary_rejects_risk_above_ceiling(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.LOW
    )

    with pytest.raises(AuthorizationError):
        boundary.authorize(
            caller, requested_scope=sample_tenant_scope, requested_risk=RiskLevel.HIGH
        )


def test_authorization_boundary_rejects_scope_outside_delegation(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.HIGH
    )
    other_tenant_scope = TenantScope(tenant_id="other-tenant")

    with pytest.raises(AuthorizationError):
        boundary.authorize(
            caller, requested_scope=other_tenant_scope, requested_risk=RiskLevel.LOW
        )