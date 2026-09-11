"""Receives HITL approvals, rejections, and revisions."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    """The transport-layer shape of an incoming human approval decision."""

    approved: bool
    approver: str
    revision_notes: str | None = None


class ApprovalDecisionResponse(BaseModel):
    """The transport-layer shape of a recorded approval decision."""

    preview_id: str
    approved: bool
    approver: str


@router.post("/{preview_id}/decide", response_model=ApprovalDecisionResponse)
async def decide_approval(
    preview_id: str, decision: ApprovalDecisionRequest, request: Request
) -> ApprovalDecisionResponse:
    """Record a human reviewer's decision on a pending action preview."""

    hitl_coordinator = request.app.state.hitl_coordinator
    recorded = hitl_coordinator.decide(
        preview_id,
        approved=decision.approved,
        approver=decision.approver,
        revision_notes=decision.revision_notes,
    )
    return ApprovalDecisionResponse(
        preview_id=recorded.preview_id, approved=recorded.approved, approver=recorded.approver
    )