"""X publishing and engagement adapter."""

from __future__ import annotations

from app.integrations.social.base import SocialAdapter

_API_BASE = "https://api.x.com/2"


class XAdapter(SocialAdapter):
    """Adapter for the X API."""

    channel = "x"

    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        response = await self._client.post(
            f"{_API_BASE}/tweets",
            json={"text": payload.get("text", "")},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}