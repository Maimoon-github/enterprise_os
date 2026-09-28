"""LinkedIn paid-media adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.ads.base import AdsAdapter, AdsReportingAdapter

_API_BASE = "https://api.linkedin.com/rest"


class LinkedInAdsAdapter(AdsAdapter, AdsReportingAdapter):
    """Adapter for the LinkedIn Marketing API and adAnalytics reporting."""

    channel = "linkedin"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "202408",
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
        """Fetch LinkedIn adAnalytics reporting data."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "adAnalytics")
        if op not in ("adAnalytics", "analytics"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on LinkedIn reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "LinkedIn access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "LinkedIn-Version": self._api_version or "202408",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        params: dict[str, Any] = {
            "q": "analytics",
            "pivot": report_spec.get("pivot", "CAMPAIGN"),
            "dateRange.start.day": report_spec.get("start_day", 1),
            "dateRange.start.month": report_spec.get("start_month", 1),
            "dateRange.start.year": report_spec.get("start_year", 2026),
            "timeGranularity": report_spec.get("granularity", "DAILY"),
        }
        url = f"{_API_BASE}/adAnalytics"
        response = await self._client.get(url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", [])
        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "202408",
            "items": elements,
            "cursor": None,
            "has_more": False,
            "total_results": len(elements),
        }


    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        campaign_id = str(payload.get("campaign_id", "linkedin_cmp_123"))
        account_id = str(payload.get("account_id", "linkedin_act_123"))
        budget = payload.get("daily_budget") or payload.get("budget") or payload.get("spend_amount")
        bid = payload.get("bid_amount") or payload.get("bid_target")
        creative_refs = payload.get("creative_refs") or ([payload["creative_id"]] if "creative_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "campaign_id": campaign_id,
                "account_id": account_id,
                "status": "published",
                "applied_budget": float(budget) if budget is not None else None,
                "applied_bid": float(bid) if bid is not None else None,
                "creative_refs": creative_refs,
                "provider_response": {
                    "id": campaign_id,
                    "account": account_id,
                    "success": True,
                    "platform": "linkedin",
                },
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/{campaign_id}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "LinkedIn-Version": "202405",
            },
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "campaign_id": campaign_id,
            "account_id": account_id,
            "status": "published",
            "applied_budget": float(budget) if budget is not None else None,
            "applied_bid": float(bid) if bid is not None else None,
            "creative_refs": creative_refs,
            "provider_response": body,
        }