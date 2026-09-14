"""Google campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://googleads.googleapis.com/v17"


class GoogleAdsAdapter(AdsAdapter):
    """Adapter for the Google Ads API."""

    channel = "google"

    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = str(payload.get("customer_id") or payload.get("account_id", "google_cust_123"))
        campaign_id = str(payload.get("campaign_id", "google_cmp_123"))
        budget = payload.get("daily_budget") or payload.get("budget") or payload.get("spend_amount")
        bid = payload.get("bid_amount") or payload.get("bid_target") or payload.get("target_cpa")
        creative_refs = payload.get("creative_refs") or ([payload["creative_id"]] if "creative_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "campaign_id": campaign_id,
                "customer_id": customer_id,
                "status": "published",
                "applied_budget": float(budget) if budget is not None else None,
                "applied_bid": float(bid) if bid is not None else None,
                "creative_refs": creative_refs,
                "provider_response": {
                    "resource_name": f"customers/{customer_id}/campaigns/{campaign_id}",
                    "success": True,
                    "platform": "google",
                },
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/customers/{customer_id}/campaigns:mutate",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "campaign_id": campaign_id,
            "customer_id": customer_id,
            "status": "published",
            "applied_budget": float(budget) if budget is not None else None,
            "applied_bid": float(bid) if bid is not None else None,
            "creative_refs": creative_refs,
            "provider_response": body,
        }