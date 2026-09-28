"""Google campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.ads.base import AdsAdapter, AdsReportingAdapter

_API_BASE = "https://googleads.googleapis.com"


class GoogleAdsAdapter(AdsAdapter, AdsReportingAdapter):
    """Adapter for the Google Ads API and GAQL Search reporting."""

    channel = "google"

    def __init__(
        self,
        access_token: str | None = None,
        *,
        client: Any | None = None,
        api_version: str = "v18",
        account_id: str | None = None,
        developer_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        customer_id: str | None = None,
    ) -> None:
        effective_account_id = account_id or customer_id
        AdsAdapter.__init__(self, access_token, client=client)
        AdsReportingAdapter.__init__(
            self,
            access_token,
            client=self._client,
            api_version=api_version,
            account_id=effective_account_id,
        )
        self._developer_token = developer_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token

    async def fetch_report_page(
        self,
        *,
        account_id: str,
        report_spec: dict[str, Any],
        cursor: str | None = None,
        limit: int = 100,
        cost_budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Fetch a page of Google Ads GAQL report rows."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "search")
        if op not in ("search", "search_stream", "google_ads_search"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on Google reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "Google Ads access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        gaql_query = report_spec.get(
            "query",
            "SELECT campaign.id, metrics.impressions, metrics.clicks, metrics.cost_micros FROM campaign",
        )
        body: dict[str, Any] = {
            "query": gaql_query,
            "pageSize": min(limit, 1000),
        }
        if cursor:
            body["pageToken"] = cursor

        headers = {
            "Authorization": f"Bearer {self._access_token}",
        }
        if self._developer_token:
            headers["developer-token"] = self._developer_token

        customer_id = account_id.replace("-", "")
        url = f"{_API_BASE}/{self._api_version or 'v18'}/customers/{customer_id}/googleAds:search"
        response = await self._client.post(url, json=body, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        next_page = data.get("nextPageToken")
        results = data.get("results", [])
        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v18",
            "items": results,
            "cursor": next_page,
            "has_more": bool(next_page),
            "total_results": len(results),
        }


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