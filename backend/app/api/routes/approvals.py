"""Receives HITL approvals, rejections, and revisions."""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class DevelopmentDecisionRequest(BaseModel):
    """The transport-layer shape of an incoming human approval decision for W_DEV."""

    task_id: str
    workflow_id: str
    step_id: str
    attempt_id: str
    subagent_id: str
    reviewer_id: str
    reviewer_role: str = "engineering"
    decision: str = "APPROVE"  # "APPROVE", "REJECT", "REQUEST_REVISION"
    input_snapshot_hash: str
    output_snapshot_hash: str
    review_dossier_hash: str
    signature: str | None = None
    private_key_pem: str | None = None
    nonce: str | None = None
    version: str = "1.0"
    revision_notes: str | None = None
    machine_policy_allowed: bool = True
    expires_in_seconds: int = 3600


class DevelopmentDecisionResponse(BaseModel):
    """The transport-layer response containing the cryptographically sealed approval token."""

    token_id: str
    task_id: str
    step_id: str
    attempt_id: str
    decision: str
    approved: bool
    reviewer_id: str
    reviewer_role: str
    signature: str
    created_at: datetime
    expires_at: datetime


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
    decided_at: datetime | None = None


class ApprovalDecisionResponse(BaseModel):
    """The transport-layer shape of a recorded approval decision."""

    preview_id: str
    approved: bool
    decision: str = "APPROVE"
    approver: str
    approver_role: str = "admin"
    clearance_id: str | None = None


@router.post("/development/decide", response_model=DevelopmentDecisionResponse)
async def decide_development(
    decision: DevelopmentDecisionRequest, request: Request
) -> DevelopmentDecisionResponse:
    """Record and cryptographically seal an authenticated human review decision for W_DEV."""
    hitl_coordinator = getattr(request.app.state, "hitl_coordinator", None)
    if hitl_coordinator is None:
        from app.services.hitl import HitlCoordinator
        hitl_coordinator = HitlCoordinator()
        try:
            request.app.state.hitl_coordinator = hitl_coordinator
        except Exception:
            pass
    validator = getattr(request.app.state, "cryptographic_validator", None)

    token = hitl_coordinator.decide_development_step(
        task_id=decision.task_id,
        workflow_id=decision.workflow_id,
        step_id=decision.step_id,
        attempt_id=decision.attempt_id,
        subagent_id=decision.subagent_id,
        reviewer_id=decision.reviewer_id,
        reviewer_role=decision.reviewer_role,
        decision=decision.decision,
        input_snapshot_hash=decision.input_snapshot_hash,
        output_snapshot_hash=decision.output_snapshot_hash,
        review_dossier_hash=decision.review_dossier_hash,
        signature=decision.signature,
        private_key_pem=decision.private_key_pem,
        nonce=decision.nonce,
        version=decision.version,
        revision_notes=decision.revision_notes or "",
        machine_policy_allowed=decision.machine_policy_allowed,
        expires_in_seconds=decision.expires_in_seconds,
        validator=validator,
    )

    task_state_service = getattr(request.app.state, "task_state_service", None)
    if task_state_service:
        tenant_id = getattr(request.state, "tenant_id", "default")
        await task_state_service.record_development_approval_decision(
            tenant_id=tenant_id,
            task_id=decision.task_id,
            approval_token=token,
        )

    return DevelopmentDecisionResponse(
        token_id=token.token_id,
        task_id=token.task_id,
        step_id=token.step_id,
        attempt_id=token.attempt_id,
        decision=token.decision,
        approved=(token.decision == "APPROVE"),
        reviewer_id=token.reviewer_id,
        reviewer_role=token.reviewer_role,
        signature=token.signature,
        created_at=token.created_at,
        expires_at=token.expires_at,
    )


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
        decided_at=decision.decided_at,
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