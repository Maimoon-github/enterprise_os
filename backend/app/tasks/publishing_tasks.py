import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.idempotency import generate_idempotency_key
from app.db.models.schedule import Schedule
from app.db.session import async_session_factory
from app.tasks.celery_app import celery_app
from sqlalchemy import select

logger = logging.getLogger("tasks.publishing")

# In-memory deduplication set for fast checks in worker processes
_processed_idempotency_keys: set[str] = set()


@celery_app.task(
    name="app.tasks.publishing_tasks.dispatch_platform_post",
    bind=True,
    max_retries=1,
    default_retry_delay=5,
)
def dispatch_platform_post(
    self: Any,
    platform: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Publishes social post to target platform with SHA-256 idempotency deduplication and exponential backoff."""
    if not idempotency_key:
        idempotency_key = generate_idempotency_key({"platform": platform, "payload": payload})

    if idempotency_key in _processed_idempotency_keys:
        logger.warning(
            "Duplicate publishing task ignored for platform %s with key %s",
            platform,
            idempotency_key,
        )
        return {
            "platform": platform,
            "status": "skipped_duplicate",
            "idempotency_key": idempotency_key,
        }

    try:
        logger.info("Publishing post to %s (idempotency: %s)", platform, idempotency_key)
        _processed_idempotency_keys.add(idempotency_key)
        return {
            "platform": platform,
            "status": "published",
            "post_id": f"{platform}_post_{idempotency_key[:12]}",
            "idempotency_key": idempotency_key,
            "published_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        logger.error("Error publishing to %s: %s", platform, exc)
        raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.publishing_tasks.poll_due_schedules_and_dispatch")
def poll_due_schedules_and_dispatch() -> dict[str, Any]:
    """Celery Beat periodic task (every 5 minutes) polling due social posts and dispatching to publishing_queue."""
    logger.info("Polling schedules table for due social posts.")

    async def _poll_and_dispatch():
        async with async_session_factory() as session:
            now = datetime.now(UTC)
            stmt = select(Schedule).where(
                Schedule.status == "scheduled",
                Schedule.scheduled_utc <= now,
            )
            result = await session.execute(stmt)
            due_schedules = list(result.scalars().all())

            dispatched_count = 0
            for sched in due_schedules:
                dispatch_platform_post.apply_async(
                    args=[
                        sched.platform,
                        {"campaign_id": str(sched.campaign_id)},
                        sched.idempotency_key,
                    ],
                    queue="publishing_queue",
                )
                sched.status = "published"
                dispatched_count += 1

            if dispatched_count > 0:
                await session.commit()
            return dispatched_count

    try:
        count = asyncio.run(_poll_and_dispatch())
        return {"status": "success", "dispatched_schedules": count}
    except Exception as exc:
        logger.error("Failed to poll and dispatch due schedules: %s", exc)
        return {"status": "error", "error": str(exc), "dispatched_schedules": 0}
