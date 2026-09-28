"""X publishing and engagement adapter."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.integrations.social.base import SocialAdapter, SocialReportingAdapter

_API_BASE = "https://api.x.com/2"


class XAdapter(SocialAdapter, SocialReportingAdapter):
    """Adapter for the X API and post/media metrics reporting."""

    channel = "x"

    def __init__(
        self,
        access_token: str | None,
        *,
        client: Any | None = None,
        api_version: str = "2",
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
        """Fetch X v2 tweet and media metrics."""
        if self._account_id and account_id != self._account_id:
            raise PolicyViolationError(
                f"Account mismatch: requested '{account_id}', bound to '{self._account_id}'."
            )
        op = report_spec.get("operation", "tweet_metrics")
        if op not in ("tweet_metrics", "user_tweets", "tweets"):
            raise PolicyViolationError(f"Operation '{op}' not permitted on X reporting interface.")
        if cost_budget_remaining is not None and cost_budget_remaining <= 0:
            raise PolicyViolationError("Authorized collection-cost budget exhausted.")
        if self._access_token is None:
            raise ConfigurationError(
                "X access token is not configured; simulated provider success is forbidden in production telemetry."
            )

        headers = {"Authorization": f"Bearer {self._access_token}"}
        params: dict[str, Any] = {
            "max_results": min(limit, 100),
            "tweet.fields": report_spec.get(
                "tweet.fields",
                "public_metrics,organic_metrics,created_at",
            ),
        }
        if cursor:
            params["pagination_token"] = cursor

        url = f"{_API_BASE}/users/{account_id}/tweets"
        response = await self._client.get(url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        meta = data.get("meta", {})
        next_token = meta.get("next_token")
        return {
            "channel": self.channel,
            "account_id": account_id,
            "api_version": self._api_version or "2",
            "items": data.get("data", []),
            "cursor": next_token,
            "has_more": bool(next_token),
            "meta": meta,
        }


    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("scheduled_at") or payload.get("scheduled_time"):
            raise PolicyViolationError(
                "Channel 'x' does not support native automated scheduling on the standard publishing endpoint; cannot silently publish immediately."
            )

        post_id = str(payload.get("post_id", "x_tweet_12345"))
        text = str(payload.get("text") or payload.get("copy", ""))

        if self._access_token is None:
            return {
                "status_code": "200",
                "channel": self.channel,
                "post_id": post_id,
                "status": "published",
                "text": text,
                "provider_response": {"id": post_id, "text": text, "platform": "x"},
                "details": {"simulated": True},
            }

        response = await self._client.post(
            f"{_API_BASE}/tweets",
            json={"text": text},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        response.raise_for_status()
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status_code": str(response.status_code),
            "channel": self.channel,
            "post_id": str(body.get("data", {}).get("id", post_id)),
            "status": "published",
            "provider_response": body,
        }


XSocialAdapter = XAdapter