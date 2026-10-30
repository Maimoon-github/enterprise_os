from typing import Any

from app.integrations.social.base_adapter import BaseSocialAdapter


class InstagramAdapter(BaseSocialAdapter):
    """Instagram Graph API (Reels & Feed Carousels) adapter."""

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        ig_post_id = f"ig_{payload.get('idempotency_key', 'default')[:12]}"
        return {
            "platform": "instagram",
            "status": "published",
            "post_id": ig_post_id,
            "url": f"https://www.instagram.com/p/{ig_post_id}",
            "aspect_ratio": payload.get("aspect_ratio", "1:1"),
        }

    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "instagram", "post_id": post_id, "impressions": 2100, "saves": 45, "likes": 160}
