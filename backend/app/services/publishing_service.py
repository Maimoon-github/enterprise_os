import logging
from typing import Any

from app.core.idempotency import generate_idempotency_key
from app.tasks.publishing_tasks import dispatch_platform_post

logger = logging.getLogger("services.publishing")


class PublishingService:
    """Manages outbound multi-platform social publication with idempotent deduplication and queue dispatch."""

    async def publish_single_post(
        self,
        platform: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Publish a single post to platform, enqueuing to Celery publishing_queue."""
        key = idempotency_key or generate_idempotency_key({"platform": platform, "payload": payload})
        task_res = dispatch_platform_post.apply_async(
            args=[platform, payload, key],
            queue="publishing_queue",
        )
        return {
            "status": "queued",
            "task_id": task_res.id,
            "platform": platform,
            "idempotency_key": key,
        }

    async def fanout_publish(
        self,
        campaign_id: str,
        platform_payloads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fan-out publish across multiple social platforms in parallel via Celery publishing_queue."""
        dispatched: list[dict[str, Any]] = []
        for p in platform_payloads:
            platform = p.get("platform", "generic")
            key = p.get("idempotency_key") or generate_idempotency_key(
                {"campaign_id": campaign_id, "platform": platform, "payload": p}
            )
            task_res = dispatch_platform_post.apply_async(
                args=[platform, p, key],
                queue="publishing_queue",
            )
            dispatched.append({
                "platform": platform,
                "status": "enqueued",
                "task_id": task_res.id,
                "idempotency_key": key,
            })
        return dispatched
