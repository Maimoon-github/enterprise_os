"""Meta campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.ads.base import AdsAdapter, AdsReportingAdapter

_API_BASE = "https://graph.facebook.com"


class MetaAdsAdapter(AdsAdapter, AdsReportingAdapter):
    """Adapter for the Meta Marketing API and Ads Insights reporting."""

    channel = "meta"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "v19.0",
        account_id: str | None = None,
    ) -> None:
        AdsAdapter.__init__(self, access_token, client=client)
        AdsReportingAdapter.__init__(
            self,
            access_token,
            client=self._client,
            api_version=api_version,
            account_id=account_id,
        )

    async def fetch_report_page(
        self,
        *,
        account_id: str,
        report_spec: dict[str, Any],
        cursor: str | None = None,
        limit: int = 100,
        cost_budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Fetch a page of Meta Ads Insights."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "insights")
        if op not in ("insights", "ad_insights"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on Meta reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "Meta Ads access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        params: dict[str, Any] = {
            "access_token": self._access_token,
            "limit": min(limit, 100),
            "level": report_spec.get("level", "campaign"),
            "fields": report_spec.get("fields", "campaign_id,impressions,clicks,spend"),
        }
        if cursor:
            params["after"] = cursor

        url = f"{_API_BASE}/{self._api_version or 'v19.0'}/{account_id}/insights"
        response = await self._client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        paging = data.get("paging", {})
        cursors = paging.get("cursors", {})
        next_cursor = cursors.get("after")
        has_more = "next" in paging and bool(next_cursor)
        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v19.0",
            "items": data.get("data", []),
            "cursor": next_cursor,
            "has_more": has_more,
            "paging": paging,
        }


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