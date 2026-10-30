import contextlib
import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.approval_repo import ApprovalRepository
from app.schemas.approval import ApprovalResponse, ApprovalResumeRequest
from app.services.approval_service import ApprovalService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
approval_service = ApprovalService()


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status_filter: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List approval requests, optionally filtered by status ('pending')."""
    repo = ApprovalRepository(db)
    if status_filter == "pending":
        return await repo.list_pending()
    return await repo.list_all(limit=limit, offset=offset)


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve details for a single approval gate request."""
    repo = ApprovalRepository(db)
    approval = await repo.get(approval_id)
    if not approval:
        raise EntityNotFoundError("Approval", str(approval_id))
    return approval


@router.post("/{approval_id}/resume", response_model=dict[str, Any])
async def resume_approval(
    approval_id: uuid.UUID,
    payload: ApprovalResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    """Resume a paused LangGraph execution with an operator decision (approved or rejected)."""
    reviewer_id = None
    with contextlib.suppress(ValueError, TypeError):
        reviewer_id = uuid.UUID(current_user["id"])

    return await approval_service.process_decision(
        approval_id=approval_id,
        approved=payload.approved,
        db=db,
        notes=payload.notes,
        modifications=payload.modifications,
        reviewer_id=reviewer_id,
    )
