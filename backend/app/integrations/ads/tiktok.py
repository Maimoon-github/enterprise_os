"""TikTok campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokAdsAdapter(AdsAdapter):
    """Adapter for the TikTok Business Ads API."""

    channel = "tiktok"

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        response = await self._client.post(
            f"{_API_BASE}/campaign/update/",
            json=payload,
            headers={"Access-Token": self._access_token or ""},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}