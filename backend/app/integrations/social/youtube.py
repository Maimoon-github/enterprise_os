"""YouTube publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.social.base import SocialAdapter, SocialReportingAdapter

_API_BASE = "https://www.googleapis.com/upload/youtube/v3"
_ANALYTICS_API_BASE = "https://youtubeanalytics.googleapis.com/v2"


class YouTubeAdapter(SocialAdapter, SocialReportingAdapter):
    """Adapter for the YouTube Data API and YouTube Analytics reports.query."""

    channel = "youtube"

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
        limit: int = 100,
        cost_budget_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Fetch YouTube Analytics reports.query."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "reports_query")
        if op not in ("reports_query", "reports"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on YouTube reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "YouTube access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        headers = {"Authorization": f"Bearer {self._access_token}"}
        start_index = int(cursor) if (cursor and cursor.isdigit()) else 1
        params: dict[str, Any] = {
            "ids": f"channel=={account_id}",
            "metrics": report_spec.get("metrics", "views,comments,likes,estimatedMinutesWatched"),
            "startDate": report_spec.get("start_date", "2026-01-01"),
            "endDate": report_spec.get("end_date", "2026-01-31"),
            "startIndex": start_index,
            "maxResults": min(limit, 100),
        }
        url = f"{_ANALYTICS_API_BASE}/reports"
        response = await self._client.get(url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        rows = data.get("rows", [])
        has_more = len(rows) >= min(limit, 100)
        next_cursor = str(start_index + len(rows)) if has_more else None

        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "v2",
            "items": rows,
            "column_headers": data.get("columnHeaders", []),
            "cursor": next_cursor,
            "has_more": has_more,
        }


    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        video_id = str(payload.get("video_id", "yt_video_12345"))
        raw_snippet = payload.get("snippet")
        snippet: dict[str, Any] = raw_snippet if isinstance(raw_snippet, dict) else {}
        raw_status = payload.get("status")
        status_dict: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
        is_scheduled = bool(payload.get("scheduled_at") or status_dict.get("publishAt"))
        status = "scheduled" if is_scheduled else "published"
        media_assets = payload.get("media_asset_ids") or ([payload["video_id"]] if "video_id" in payload else [])

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": video_id,
                "video_id": video_id,
                "status": status,
                "title": str(snippet.get("title") or payload.get("title", "")),
                "media_asset_ids": media_assets,
                "scheduled_at": str(payload.get("scheduled_at") or status_dict.get("publishAt", "")),
                "provider_response": {"id": video_id, "status": status, "platform": "youtube"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/videos",
            params={"part": "snippet,status"},
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("id", video_id)),
            "video_id": str(body.get("id", video_id)),
            "status": status,
            "provider_response": body,
        }


YouTubeSocialAdapter = YouTubeAdapter