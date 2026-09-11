"""Receives HITL approvals, rejections, and revisions."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.action_preview import ApprovalDecision
from app.services.hitl import HitlService

router = APIRouter()


@router.post("/{preview_id}", status_code=status.HTTP_202_ACCEPTED)
async def decide(preview_id: str, decision: ApprovalDecision) -> dict[str, str]:
    HitlService().record(preview_id, decision)
    return {"status": "recorded", "preview_id": preview_id}
