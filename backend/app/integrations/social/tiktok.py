"""TikTok social publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokSocialAdapter(SocialAdapter):
    """Adapter for the TikTok Content Posting API."""

    channel = "tiktok"

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        publish_id = str(payload.get("publish_id", "tt_pub_12345"))
        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": publish_id,
                "publish_id": publish_id,
                "status": "published",
                "provider_response": {"publish_id": publish_id, "platform": "tiktok"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/post/publish/video/init/",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("data", {}).get("publish_id", publish_id)),
            "publish_id": str(body.get("data", {}).get("publish_id", publish_id)),
            "status": "published",
            "provider_response": body,
        }