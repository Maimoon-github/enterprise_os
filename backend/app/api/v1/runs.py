import asyncio
import json
import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.run_repo import RunRepository
from app.schemas.run import RunCreate, RunResponse
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_run(
    payload: RunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    thread_id = f"thread_{uuid.uuid4().hex[:16]}"
    repo = RunRepository(db)
    run = await repo.create(
        campaign_id=payload.campaign_id,
        thread_id=thread_id,
        status="running",
        trigger_type="manual",
        current_node="supervisor_router",
        token_usage={},
    )
    return run


@router.get("", response_model=list[RunResponse])
async def list_runs(
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
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
    async def event_generator():
        nodes = [
            "supervisor_router",
            "research_strategy",
            "campaign_creative",
            "human_approval_gate",
        ]
        for idx, node in enumerate(nodes):
            await asyncio.sleep(0.3)
            payload = {
                "run_id": run_id,
                "node": node,
                "step": idx + 1,
                "status": "executing",
            }
            yield f"event: node_transition\ndata: {json.dumps(payload)}\n\n"

        yield 'event: complete\ndata: {"status": "interrupted", "reason": "human_approval_required"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
