"""Instagram publishing and engagement adapter."""

from __future__ import annotations

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://graph.facebook.com/v19.0"


class InstagramAdapter(SocialAdapter):
    """Adapter for the Instagram Graph API."""

    channel = "instagram"

    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        ig_user_id = payload["ig_user_id"]
        response = await self._client.post(
            f"{_API_BASE}/{ig_user_id}/media",
            data={**payload, "access_token": self._access_token},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}