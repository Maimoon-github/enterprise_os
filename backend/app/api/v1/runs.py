import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.run_repo import RunRepository
from app.schemas.run import RunCreate, RunResponse
from app.services.run_service import RunService
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
run_service = RunService()


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_run(
    payload: RunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    """Dispatch a new orchestrator run for a campaign."""
    return await run_service.dispatch_orchestrator(
        campaign_id=payload.campaign_id,
        db=db,
        user_command=payload.user_command,
        skills_override=payload.skills_override,
    )


@router.get("", response_model=list[RunResponse])
async def list_runs(
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List runs filtered by campaign or paginated."""
    repo = RunRepository(db)
    if campaign_id:
        return await repo.list_by_campaign(campaign_id)
    return await repo.list_all(limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve run by UUID or thread_id."""
    repo = RunRepository(db)
    try:
        run_uuid = uuid.UUID(run_id)
        run = await repo.get(run_uuid)
    except (ValueError, TypeError):
        run = await repo.get_by_thread_id(run_id)

    if not run:
        raise EntityNotFoundError("Run", run_id)
    return run


@router.get("/{run_id}/stream")
async def stream_run_execution(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Stream LangGraph execution events via Server-Sent Events (SSE)."""
    return StreamingResponse(
        run_service.stream_run_execution(run_id=run_id, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        },
    )
