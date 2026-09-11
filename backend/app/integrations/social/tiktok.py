"""TikTok social publishing and engagement adapter."""

from __future__ import annotations

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokSocialAdapter(SocialAdapter):
    """Adapter for the TikTok Content Posting API."""

    channel = "tiktok"

    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        response = await self._client.post(
            f"{_API_BASE}/post/publish/video/init/",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}