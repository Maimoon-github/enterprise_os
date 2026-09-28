"""TikTok social publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.social.base import SocialAdapter, SocialReportingAdapter

_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokSocialAdapter(SocialAdapter, SocialReportingAdapter):
    """Adapter for the TikTok Content Posting and Display v2 video reporting."""

    channel = "tiktok"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "v2",
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
        limit: int = 20,
        cost_budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Fetch a page of owned public videos from TikTok Display v2."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "video_list")
        if op not in ("video_list", "video_query"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on TikTok social reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "TikTok Social access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        headers = {"Authorization": f"Bearer {self._access_token}"}
        body: dict[str, Any] = {
            "max_count": min(limit, 20),
            "fields": report_spec.get("fields", ["id", "title", "like_count", "comment_count", "share_count", "view_count"]),
        }
        if cursor:
            body["cursor"] = int(cursor) if cursor.isdigit() else cursor

        url = f"{_API_BASE}/video/list/"
        response = await self._client.post(url, json=body, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        inner_data = data.get("data", {})
        has_more = inner_data.get("has_more", False)
        next_cursor = str(inner_data.get("cursor")) if has_more else None

        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v2",
            "items": inner_data.get("videos", []),
            "cursor": next_cursor,
            "has_more": has_more,
        }


    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        publish_id = str(payload.get("publish_id", "tt_pub_12345"))
        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": publish_id,
                "publish_id": publish_id,
                "status": "published",
                "provider_response": {"publish_id": publish_id, "platform": "tiktok"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/post/publish/video/init/",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("data", {}).get("publish_id", publish_id)),
            "publish_id": str(body.get("data", {}).get("publish_id", publish_id)),
            "status": "published",
            "provider_response": body,
        }