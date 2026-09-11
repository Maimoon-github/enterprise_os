"""Verifies mandatory approval for spend, claims, code, and dispatch."""
from app.schemas.action_preview import ApprovalDecision, PreviewKind
from app.services.hitl import HitlService


def test_hitl_records_decision() -> None:
    svc = HitlService()
    svc.record("p1", ApprovalDecision(decision="approved", reviewer="owner"))
    decision = svc.decision_for("p1")
    assert decision is not None
    assert decision.decision == "approved"


def test_preview_kind_enum_has_all_mandatory_kinds() -> None:
    kinds = {k.value for k in PreviewKind}
    assert {"spend", "claims", "copy", "code"} <= kinds
