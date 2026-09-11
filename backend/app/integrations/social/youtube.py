"""YouTube publishing and engagement adapter."""

from __future__ import annotations

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://www.googleapis.com/upload/youtube/v3"


class YouTubeAdapter(SocialAdapter):
    """Adapter for the YouTube Data API."""

    channel = "youtube"

    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        response = await self._client.post(
            f"{_API_BASE}/videos",
            params={"part": "snippet,status"},
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}