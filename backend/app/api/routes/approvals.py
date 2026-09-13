"""Receives HITL approvals, rejections, and revisions."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    """The transport-layer shape of an incoming human approval decision."""

    approved: bool = True
    decision: str | None = None
    approver: str
    approver_role: str = "admin"
    tenant_id: str | None = None
    signature: str | None = None
    preview_content_hash: str | None = None
    revision_notes: str | None = None


class ApprovalDecisionResponse(BaseModel):
    """The transport-layer shape of a recorded approval decision."""

    preview_id: str
    approved: bool
    decision: str = "APPROVE"
    approver: str
    approver_role: str = "admin"
    clearance_id: str | None = None


@router.post("/{preview_id}/decide", response_model=ApprovalDecisionResponse)
async def decide_approval(
    preview_id: str, decision: ApprovalDecisionRequest, request: Request
) -> ApprovalDecisionResponse:
    """Record a human reviewer's authenticated decision on a pending action preview."""

    hitl_coordinator = request.app.state.hitl_coordinator
    validator = getattr(request.app.state, "cryptographic_validator", None)

    recorded = hitl_coordinator.decide(
        preview_id,
        approved=decision.approved,
        decision=decision.decision,
        approver=decision.approver,
        approver_role=decision.approver_role,
        tenant_id=decision.tenant_id,
        signature=decision.signature,
        preview_content_hash=decision.preview_content_hash,
        revision_notes=decision.revision_notes,
        validator=validator,
    )
    decision_val = recorded.decision.value if hasattr(recorded.decision, "value") else str(recorded.decision)
    clearance_id = recorded.clearance.clearance_id if recorded.clearance else None

    return ApprovalDecisionResponse(
        preview_id=recorded.preview_id,
        approved=recorded.approved,
        decision=decision_val,
        approver=recorded.approver,
        approver_role=recorded.approver_role,
        clearance_id=clearance_id,
    )