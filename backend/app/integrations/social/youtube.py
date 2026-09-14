"""YouTube publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://www.googleapis.com/upload/youtube/v3"


class YouTubeAdapter(SocialAdapter):
    """Adapter for the YouTube Data API."""

    channel = "youtube"

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        video_id = str(payload.get("video_id", "yt_video_12345"))
        snippet = payload.get("snippet") if isinstance(payload.get("snippet"), dict) else {}
        status_dict = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        is_scheduled = bool(payload.get("scheduled_at") or status_dict.get("publishAt"))
        status = "scheduled" if is_scheduled else "published"
        media_assets = payload.get("media_asset_ids") or ([payload["video_id"]] if "video_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": video_id,
                "video_id": video_id,
                "status": status,
                "title": str(snippet.get("title") or payload.get("title", "")),
                "media_asset_ids": media_assets,
                "scheduled_at": str(payload.get("scheduled_at") or status_dict.get("publishAt", "")),
                "provider_response": {"id": video_id, "status": status, "platform": "youtube"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/videos",
            params={"part": "snippet,status"},
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("id", video_id)),
            "video_id": str(body.get("id", video_id)),
            "status": status,
            "provider_response": body,
        }


YouTubeSocialAdapter = YouTubeAdapter