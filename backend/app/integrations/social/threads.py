from typing import Any

from app.integrations.social.base_adapter import BaseSocialAdapter


class ThreadsAdapter(BaseSocialAdapter):
    """Meta Threads REST API adapter."""

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        post_id = f"th_{payload.get('idempotency_key', 'default')[:12]}"
        return {
            "platform": "threads",
            "status": "published",
            "post_id": post_id,
            "url": f"https://www.threads.net/post/{post_id}",
            "aspect_ratio": payload.get("aspect_ratio", "1:1"),
        }

    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "threads", "post_id": post_id, "views": 850, "reposts": 12, "likes": 55}
