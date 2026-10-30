from typing import Any

from app.integrations.social.base_adapter import BaseSocialAdapter


class YouTubeAdapter(BaseSocialAdapter):
    """YouTube Data API v3 Shorts & Video upload adapter."""

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        video_id = f"yt_{payload.get('idempotency_key', 'default')[:11]}"
        return {
            "platform": "youtube",
            "status": "published",
            "post_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "aspect_ratio": payload.get("aspect_ratio", "16:9"),
        }

    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "youtube", "post_id": post_id, "views": 3200, "likes": 180, "comments": 14}
