"""Verifies policy decisions and monotonic attenuation."""
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.schemas.governance import Budget, PolicyEnvelope, RiskEnvelope
from app.security.scope_evaluator import ScopeEvaluator


def _envelope(spend: float, max_spend: float) -> PolicyEnvelope:
    return PolicyEnvelope(
        policy_id="p1",
        directive_id="d1",
        tenant_id="t1",
        scopes=["read"],
        budget=Budget(amount=spend),
        risk=RiskEnvelope(max_spend=max_spend, max_risk_score=0.5),
    )


def test_policy_rejects_budget_over_risk() -> None:
    assert PolicyEvaluator().evaluate(_envelope(100, 50)).allowed is False


def test_policy_allows_budget_within_risk() -> None:
    assert PolicyEvaluator().evaluate(_envelope(10, 50)).allowed is True


def test_scope_attenuation_is_monotonic() -> None:
    attenuated = ScopeEvaluator().attenuate({"a", "b", "c"}, {"b", "c", "d"})
    assert attenuated == {"b", "c"}
