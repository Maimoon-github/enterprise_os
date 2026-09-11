"""LinkedIn paid-media adapter."""

from __future__ import annotations

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://api.linkedin.com/rest/adCampaigns"


class LinkedInAdsAdapter(AdsAdapter):
    """Adapter for the LinkedIn Marketing API."""

    channel = "linkedin"

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        campaign_id = payload["campaign_id"]
        response = await self._client.post(
            f"{_API_BASE}/{campaign_id}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "LinkedIn-Version": "202405",
            },
        )
        response.raise_for_status()
        return {"status_code": str(response.status_code), "channel": self.channel}