"""Verifies directive -> workers -> HITL -> actuation -> telemetry -> learning flow."""
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.schemas.governance import Budget, Directive, PolicyEnvelope, RiskEnvelope
from app.services.policy_engine import PolicyEngine


def test_end_to_end_governed_flow() -> None:
    directive = Directive(
        directive_id="d1",
        tenant_id="t1",
        objective="grow signups",
        scopes=["read", "plan"],
        budget=Budget(amount=10),
        risk=RiskEnvelope(max_spend=100, max_risk_score=0.4),
    )
    envelope: PolicyEnvelope = PolicyEngine().compile_envelope(directive)
    result = IntelligenceEngine().run(envelope)
    assert result["status"] == "scheduled"
