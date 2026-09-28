"""Instagram publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.social.base import SocialAdapter, SocialReportingAdapter

_API_BASE = "https://graph.facebook.com"


class InstagramAdapter(SocialAdapter, SocialReportingAdapter):
    """Adapter for the Instagram Graph API and account/media Insights."""

    channel = "instagram"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "v19.0",
        account_id: str | None = None,
    ) -> None:
        SocialAdapter.__init__(self, access_token, client=client)
        SocialReportingAdapter.__init__(
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
        """Fetch Instagram account or media Insights."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "insights")
        if op not in ("insights", "media_insights"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on Instagram reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "Instagram access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        params: dict[str, Any] = {
            "access_token": self._access_token,
            "metric": report_spec.get("metric", "impressions,reach,profile_views"),
            "period": report_spec.get("period", "day"),
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
        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v19.0",
            "items": data.get("data", []),
            "cursor": next_cursor,
            "has_more": "next" in paging and bool(next_cursor),
            "paging": paging,
        }


    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        ig_user_id = str(payload.get("ig_user_id") or payload.get("account_id", "ig_user_default"))
        post_id = str(payload.get("post_id", "ig_post_12345"))
        is_scheduled = bool(payload.get("scheduled_publish_time") or payload.get("scheduled_at"))
        status = "scheduled" if is_scheduled else "published"
        media_assets = payload.get("media_asset_ids") or ([payload["media_id"]] if "media_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": post_id,
                "ig_user_id": ig_user_id,
                "status": status,
                "caption": str(payload.get("caption") or payload.get("text", "")),
                "media_asset_ids": media_assets,
                "scheduled_at": str(payload.get("scheduled_publish_time") or payload.get("scheduled_at", "")),
                "provider_response": {"id": post_id, "success": True, "platform": "instagram"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/{ig_user_id}/media",
            data={**payload, "access_token": self._access_token},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        resp = response
        data = body
        return {
            "status_code": str(resp.status_code),
            "channel": self.channel,
            "post_id": post_id,
            "ig_user_id": ig_user_id,
            "status": status,
            "media_asset_ids": media_assets,
            "provider_response": data,
        }


InstagramSocialAdapter = InstagramAdapter