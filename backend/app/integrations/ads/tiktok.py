"""TikTok campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokAdsAdapter(AdsAdapter):
    """Adapter for the TikTok Business Ads API."""

    channel = "tiktok"

    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        campaign_id = str(payload.get("campaign_id", "tiktok_cmp_123"))
        advertiser_id = str(payload.get("advertiser_id") or payload.get("account_id", "tiktok_adv_123"))
        budget = payload.get("daily_budget") or payload.get("budget") or payload.get("spend_amount")
        bid = payload.get("bid_amount") or payload.get("bid_target")
        creative_refs = payload.get("creative_refs") or ([payload["creative_id"]] if "creative_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "campaign_id": campaign_id,
                "advertiser_id": advertiser_id,
                "status": "published",
                "applied_budget": float(budget) if budget is not None else None,
                "applied_bid": float(bid) if bid is not None else None,
                "creative_refs": creative_refs,
                "provider_response": {
                    "code": 0,
                    "message": "OK",
                    "data": {"campaign_id": campaign_id},
                    "platform": "tiktok",
                },
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/campaign/update/",
            json=payload,
            headers={"Access-Token": self._access_token or ""},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "campaign_id": campaign_id,
            "advertiser_id": advertiser_id,
            "status": "published",
            "applied_budget": float(budget) if budget is not None else None,
            "applied_bid": float(bid) if bid is not None else None,
            "creative_refs": creative_refs,
            "provider_response": body,
        }