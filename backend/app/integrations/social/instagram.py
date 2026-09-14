"""Instagram publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://graph.facebook.com/v19.0"


class InstagramAdapter(SocialAdapter):
    """Adapter for the Instagram Graph API."""

    channel = "instagram"

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        ig_user_id = str(payload.get("ig_user_id") or payload.get("account_id", "ig_user_default"))
        post_id = str(payload.get("post_id", "ig_post_12345"))
        is_scheduled = bool(payload.get("scheduled_publish_time") or payload.get("scheduled_at"))
        status = "scheduled" if is_scheduled else "published"
        media_assets = payload.get("media_asset_ids") or ([payload["media_id"]] if "media_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": post_id,
                "ig_user_id": ig_user_id,
                "status": status,
                "caption": str(payload.get("caption") or payload.get("text", "")),
                "media_asset_ids": media_assets,
                "scheduled_at": str(payload.get("scheduled_publish_time") or payload.get("scheduled_at", "")),
                "provider_response": {"id": post_id, "success": True, "platform": "instagram"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/{ig_user_id}/media",
            data={**payload, "access_token": self._access_token},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        resp = response
        data = body
        return {
            "status_code": str(resp.status_code),
            "channel": self.channel,
            "post_id": post_id,
            "ig_user_id": ig_user_id,
            "status": status,
            "media_asset_ids": media_assets,
            "provider_response": data,
        }


InstagramSocialAdapter = InstagramAdapter