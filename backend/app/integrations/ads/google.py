"""Google campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://googleads.googleapis.com/v17"


class GoogleAdsAdapter(AdsAdapter):
    """Adapter for the Google Ads API."""

    channel = "google"

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        customer_id = payload["customer_id"]
        response = await self._client.post(
            f"{_API_BASE}/customers/{customer_id}/campaigns:mutate",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}