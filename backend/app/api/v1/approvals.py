import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.approval_repo import ApprovalRepository
from app.schemas.approval import ApprovalResponse, ApprovalResumeRequest
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status_filter: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
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
    repo = ApprovalRepository(db)
    approval = await repo.get(approval_id)
    if not approval:
        raise EntityNotFoundError("Approval", str(approval_id))

    reviewer_id = None
    with contextlib.suppress(ValueError, TypeError):
        reviewer_id = uuid.UUID(current_user["id"])

    new_status = "approved" if payload.approved else "rejected"

    now = datetime.now(UTC)

    await repo.update(
        approval_id,
        status=new_status,
        decision_notes=payload.notes,
        reviewed_by=reviewer_id,
        resolved_at=now,
    )

    return {
        "status": "resumed",
        "approval_id": str(approval_id),
        "thread_id": approval.thread_id,
        "decision": new_status,
        "resolved_at": now.isoformat(),
    }
