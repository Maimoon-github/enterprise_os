"""X publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import PolicyViolationError
from app.integrations.social.base import SocialAdapter

_API_BASE = "https://api.x.com/2"


class XAdapter(SocialAdapter):
    """Adapter for the X API."""

    channel = "x"

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("scheduled_at") or payload.get("scheduled_time"):
            raise PolicyViolationError(
                "Channel 'x' does not support native automated scheduling on the standard publishing endpoint; cannot silently publish immediately."
            )

        post_id = str(payload.get("post_id", "x_tweet_12345"))
        text = str(payload.get("text") or payload.get("copy", ""))

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": post_id,
                "status": "published",
                "text": text,
                "provider_response": {"id": post_id, "text": text, "platform": "x"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/tweets",
            json={"text": text},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("data", {}).get("id", post_id)),
            "status": "published",
            "provider_response": body,
        }


XSocialAdapter = XAdapter