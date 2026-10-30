from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json
import asyncio
from app.api.deps import get_db, get_current_user
from app.schemas.run import RunCreate, RunResponse
from app.db.repositories.base_repo import BaseRepository
from app.db.models.run import Run

router = APIRouter()

@router.post("", response_model=RunResponse, status_code=202)
async def dispatch_run(payload: RunCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    repo = BaseRepository(Run, db)
    run = await repo.create(
        campaign_id=payload.campaign_id,
        thread_id=thread_id,
        status="running",
        trigger_type="manual",
        current_node="supervisor_router",
    )
    return run

@router.get("/{run_id}/stream")
async def stream_run_execution(run_id: str):
    async def event_generator():
        # Blueprint SSE generator simulating node transitions
        nodes = ["supervisor_router", "research_strategy", "campaign_creative", "human_approval_gate"]
        for idx, node in enumerate(nodes):
            await asyncio.sleep(0.5)
            payload = {
                "run_id": run_id,
                "node": node,
                "step": idx + 1,
                "status": "executing",
            }
            yield f"event: node_transition\ndata: {json.dumps(payload)}\n\n"
        yield "event: complete\ndata: {\"status\": \"interrupted\", \"reason\": \"human_approval_required\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
