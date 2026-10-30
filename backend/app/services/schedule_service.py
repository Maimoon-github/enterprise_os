import logging
import uuid
from typing import Any

from app.core.exceptions import EntityNotFoundError, IdempotencyConflictError
from app.core.idempotency import generate_schedule_idempotency_key
from app.db.models.schedule import Schedule
from app.db.repositories.base_repo import BaseRepository
from app.schemas.schedule import ScheduleCreate
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE
from app.tasks.celery_app import celery_app
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("services.schedule")


class ScheduleService:
    async def list_schedules(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Schedule]:
        """List scheduled posts, optionally filtered by campaign."""
        repo = BaseRepository(Schedule, db)
        if campaign_id:
            result = await db.execute(
                select(Schedule).where(Schedule.campaign_id == campaign_id).limit(limit).offset(offset)
            )
            return list(result.scalars().all())
        return await repo.list_all(limit=limit, offset=offset)

    async def create_schedule(
        self,
        db: AsyncSession,
        payload: ScheduleCreate,
    ) -> Schedule:
        """Create and register a scheduled social post with deterministic SHA-256 idempotency key."""
        idempotency_key = generate_schedule_idempotency_key(
            campaign_id=payload.campaign_id,
            platform=payload.platform,
            scheduled_utc=payload.scheduled_utc,
        )

        result = await db.execute(select(Schedule).where(Schedule.idempotency_key == idempotency_key))
        if result.scalars().first():
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

    async def delete_schedule(self, db: AsyncSession, schedule_id: uuid.UUID) -> bool:
        """Remove a scheduled post."""
        repo = BaseRepository(Schedule, db)
        deleted = await repo.delete(schedule_id)
        if not deleted:
            raise EntityNotFoundError("Schedule", str(schedule_id))
        return True

    def list_beat_schedules(self) -> list[dict[str, Any]]:
        """Return registered Celery Beat periodic schedules."""
        schedules = []
        for name, spec in CELERY_BEAT_SCHEDULE.items():
            schedule_expr = str(spec.get("schedule", ""))
            queue = spec.get("options", {}).get("queue", "default")
            schedules.append({
                "name": name,
                "task": spec.get("task"),
                "schedule": schedule_expr,
                "queue": queue,
                "status": "active",
            })
        return schedules

    def trigger_beat_schedule(self, schedule_name: str) -> dict[str, Any]:
        """Manually dispatch a Celery Beat periodic task immediately."""
        spec = CELERY_BEAT_SCHEDULE.get(schedule_name)
        if not spec:
            raise EntityNotFoundError("BeatSchedule", schedule_name)

        task_name = spec["task"]
        queue = spec.get("options", {}).get("queue", "default")
        task = celery_app.tasks.get(task_name)
        if task:
            async_res = task.apply_async(queue=queue)
            return {"status": "triggered", "schedule_name": schedule_name, "task_id": async_res.id}
        return {"status": "triggered_by_name", "schedule_name": schedule_name, "task": task_name}
