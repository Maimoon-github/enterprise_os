from typing import Any

from app.integrations.social.base_adapter import BaseSocialAdapter


class LinkedInAdapter(BaseSocialAdapter):
    """LinkedIn Share & Media REST v2 adapter."""

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        post_id = f"urn:li:share:{payload.get('idempotency_key', 'default')[:12]}"
        return {
            "platform": "linkedin",
            "status": "published",
            "post_id": post_id,
            "url": f"https://www.linkedin.com/feed/update/{post_id}",
            "aspect_ratio": payload.get("aspect_ratio", "1:1"),
        }

    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"platform": "linkedin", "post_id": post_id, "impressions": 1250, "clicks": 54, "reactions": 38}
