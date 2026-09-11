"""Meta campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://graph.facebook.com/v19.0"


class MetaAdsAdapter(AdsAdapter):
    """Adapter for the Meta Marketing API."""

    channel = "meta"

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        campaign_id = payload["campaign_id"]
        response = await self._client.post(
            f"{_API_BASE}/{campaign_id}",
            data={**payload, "access_token": self._access_token},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}