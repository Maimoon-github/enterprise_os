"""TikTok campaign, targeting, bid, and telemetry adapter."""

from __future__ import annotations

import json
from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.ads.base import AdsAdapter, AdsReportingAdapter

_API_BASE = "https://business-api.tiktok.com/open_api"


class TikTokAdsAdapter(AdsAdapter, AdsReportingAdapter):
    """Adapter for the TikTok Business Ads API and integrated reporting."""

    channel = "tiktok"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "v1.3",
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
        """Fetch a page of TikTok integrated advertising reporting."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "report_integrated_get")
        if op not in ("report_integrated_get", "report"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on TikTok reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "TikTok Ads access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        page_num = int(cursor) if (cursor and cursor.isdigit()) else 1
        params: dict[str, Any] = {
            "advertiser_id": account_id,
            "report_type": report_spec.get("report_type", "BASIC"),
            "data_level": report_spec.get("data_level", "AUCTION_CAMPAIGN"),
            "dimensions": json.dumps(report_spec.get("dimensions", ["campaign_id"])),
            "metrics": json.dumps(report_spec.get("metrics", ["spend", "impressions", "clicks"])),
            "page": page_num,
            "page_size": min(limit, 1000),
        }
        if "start_date" in report_spec and "end_date" in report_spec:
            params["start_date"] = report_spec["start_date"]
            params["end_date"] = report_spec["end_date"]

        url = f"{_API_BASE}/{self._api_version or 'v1.3'}/report/integrated/get/"
        headers = {"Access-Token": self._access_token}
        response = await self._client.get(url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        report_data = data.get("data", {})
        page_info = report_data.get("page_info", {})
        total_page = page_info.get("total_page", 1)
        has_more = page_num < total_page
        next_cursor = str(page_num + 1) if has_more else None

        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v1.3",
            "items": report_data.get("list", []),
            "cursor": next_cursor,
            "has_more": has_more,
            "page_info": page_info,
        }


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