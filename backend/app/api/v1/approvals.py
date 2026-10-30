import uuid

from app.api.deps import get_current_user, get_db
from app.db.models.approval import Approval
from app.db.repositories.base_repo import BaseRepository
from app.schemas.approval import ApprovalResponse, ApprovalResumeRequest
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Approval, db)
    return await repo.list_all()

@router.post("/{approval_id}/resume", response_model=dict)
async def resume_approval(
    approval_id: uuid.UUID,
    payload: ApprovalResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Blueprint resumption endpoint communicating with LangGraph Command(resume=payload)
    return {
        "status": "resumed",
        "approval_id": str(approval_id),
        "decision": "approved" if payload.approved else "rejected",
    }
