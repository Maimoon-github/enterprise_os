from typing import Any

from app.integrations.social.base_adapter import BaseSocialAdapter


class GoogleBusinessProfileAdapter(BaseSocialAdapter):
    """Google Business Profile Performance & Local Post adapter."""

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        local_post_id = f"gbp_{payload.get('idempotency_key', 'default')[:12]}"
        return {
            "platform": "google_business_profile",
            "status": "published",
            "post_id": local_post_id,
            "url": f"https://business.google.com/post/{local_post_id}",
            "aspect_ratio": payload.get("aspect_ratio", "4:5"),
        }

    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "google_business_profile", "post_id": post_id, "views": 1500, "actions": 72, "calls": 8}
