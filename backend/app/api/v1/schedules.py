import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.rbac import UserRole
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.services.schedule_service import ScheduleService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
schedule_service = ScheduleService()


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List scheduled posts, optionally filtered by campaign."""
    return await schedule_service.list_schedules(db, campaign_id=campaign_id, limit=limit, offset=offset)


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    """Register a scheduled post with deterministic SHA-256 idempotency key."""
    return await schedule_service.create_schedule(db, payload=payload)


@router.get("/beat", response_model=list[dict[str, Any]])
async def list_beat_schedules(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve registered Celery Beat periodic background schedules."""
    return schedule_service.list_beat_schedules()


@router.post("/beat/{schedule_name}/trigger", response_model=dict[str, Any])
async def trigger_beat_schedule(
    schedule_name: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    """Manually dispatch a Celery Beat periodic task immediately."""
    return schedule_service.trigger_beat_schedule(schedule_name)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    """Delete a scheduled post."""
    await schedule_service.delete_schedule(db, schedule_id=schedule_id)
    return None
