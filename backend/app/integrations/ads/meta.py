"""Meta campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.ads.base import AdsAdapter

_API_BASE = "https://graph.facebook.com/v19.0"


class MetaAdsAdapter(AdsAdapter):
    """Adapter for the Meta Marketing API."""

    channel = "meta"

    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        campaign_id = str(payload.get("campaign_id", "meta_cmp_123"))
        budget = payload.get("daily_budget") or payload.get("budget") or payload.get("spend_amount")
        bid = payload.get("bid_amount") or payload.get("bid_target")
        creative_refs = payload.get("creative_refs") or ([payload["creative_id"]] if "creative_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "campaign_id": campaign_id,
                "status": "published",
                "applied_budget": float(budget) if budget is not None else None,
                "applied_bid": float(bid) if bid is not None else None,
                "creative_refs": creative_refs,
                "provider_response": {"id": campaign_id, "success": True, "platform": "meta"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/{campaign_id}",
            data={**payload, "access_token": self._access_token},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "campaign_id": campaign_id,
            "status": "published",
            "applied_budget": float(budget) if budget is not None else None,
            "applied_bid": float(bid) if bid is not None else None,
            "creative_refs": creative_refs,
            "provider_response": body,
        }