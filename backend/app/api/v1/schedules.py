import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError, IdempotencyConflictError
from app.core.idempotency import generate_schedule_idempotency_key
from app.core.rbac import UserRole
from app.db.models.schedule import Schedule
from app.db.repositories.base_repo import BaseRepository
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = BaseRepository(Schedule, db)
    if campaign_id:
        result = await db.execute(
            select(Schedule).where(Schedule.campaign_id == campaign_id).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    return await repo.list_all(limit=limit, offset=offset)


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    idempotency_key = generate_schedule_idempotency_key(
        campaign_id=payload.campaign_id,
        platform=payload.platform,
        scheduled_utc=payload.scheduled_utc,
    )

    # Check for existing idempotency key conflict
    result = await db.execute(select(Schedule).where(Schedule.idempotency_key == idempotency_key))
    existing = result.scalars().first()
    if existing:
        raise IdempotencyConflictError(
            f"Schedule already exists with idempotency key '{idempotency_key}'"
        )

    repo = BaseRepository(Schedule, db)
    schedule = await repo.create(
        campaign_id=payload.campaign_id,
        platform=payload.platform,
        cron_expression=payload.cron_expression,
        scheduled_utc=payload.scheduled_utc,
        status="scheduled",
        idempotency_key=idempotency_key,
    )
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    repo = BaseRepository(Schedule, db)
    deleted = await repo.delete(schedule_id)
    if not deleted:
        raise EntityNotFoundError("Schedule", str(schedule_id))
    return None
