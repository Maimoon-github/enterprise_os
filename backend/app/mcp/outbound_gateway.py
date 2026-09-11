"""Post-HITL signed, rate-limited actuation boundary.

This is the only module in the backend permitted to invoke an ads, social,
or CMS adapter. Every call requires: (1) a recorded, approved HITL decision
for the referenced action preview, (2) a valid signature over the dispatch
payload, and (3) available rate-limit capacity.
"""

from __future__ import annotations

import json
import time

from app.core.exceptions import (
    ConfigurationError,
    RateLimitExceededError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.cms.client import CmsClient
from app.integrations.social.base import SocialAdapter
from app.schemas.dispatch import DispatchDirective
from app.security.cryptographic_validator import CryptographicValidator
from app.services.hitl import HitlCoordinator


class TokenBucket:
    """A minimal token-bucket rate limiter."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_per_second = refill_per_second
        self._last_refill = time.monotonic()

    def allow(self) -> bool:
        """Consume one token if available and return whether it was granted."""

        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
        self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


def canonical_dispatch_bytes(dispatch: DispatchDirective) -> bytes:
    """Return the deterministic byte payload a dispatch signature must cover."""

    canonical = {
        "dispatch_id": dispatch.dispatch_id,
        "task_id": dispatch.task_id,
        "action_preview_id": dispatch.action_preview_id,
        "approved_by": dispatch.approved_by,
        "approved_at": dispatch.approved_at.isoformat(),
        "channel": dispatch.channel,
        "payload": dispatch.payload,
    }
    return json.dumps(canonical, sort_keys=True).encode("utf-8")


class OutboundGateway:
    """Enforces HITL approval, signature verification, and rate limiting before actuation."""

    def __init__(
        self,
        hitl: HitlCoordinator,
        crypto_validator: CryptographicValidator,
        *,
        ads_adapters: dict[str, AdsAdapter] | None = None,
        social_adapters: dict[str, SocialAdapter] | None = None,
        cms_client: CmsClient | None = None,
        rate_limiter: TokenBucket | None = None,
        require_signature: bool = True,
    ) -> None:
        self._hitl = hitl
        self._crypto_validator = crypto_validator
        self._ads_adapters = ads_adapters or {}
        self._social_adapters = social_adapters or {}
        self._cms_client = cms_client
        self._rate_limiter = rate_limiter or TokenBucket(capacity=10, refill_per_second=1.0)
        self._require_signature = require_signature

    async def execute(self, dispatch: DispatchDirective) -> dict[str, str]:
        """Verify approval, signature, and rate limit, then actuate ``dispatch``."""

        self._hitl.require_approved(dispatch.action_preview_id)

        if self._require_signature:
            payload_bytes = canonical_dispatch_bytes(dispatch)
            if not self._crypto_validator.verify(payload_bytes, dispatch.signature):
                raise SignatureVerificationError(
                    f"Dispatch '{dispatch.dispatch_id}' failed signature verification."
                )

        if not self._rate_limiter.allow():
            raise RateLimitExceededError(
                f"Outbound rate limit exceeded for dispatch '{dispatch.dispatch_id}'."
            )

        if dispatch.channel in self._ads_adapters:
            return await self._ads_adapters[dispatch.channel].apply_action(dispatch.payload)
        if dispatch.channel in self._social_adapters:
            return await self._social_adapters[dispatch.channel].publish(dispatch.payload)
        if dispatch.channel == "cms" and self._cms_client is not None:
            entry_id = dispatch.payload.get("entry_id", "")
            content_type = dispatch.payload.get("content_type", "")
            return await self._cms_client.apply_changes(content_type, entry_id, dispatch.payload)

        raise ConfigurationError(
            f"No outbound adapter is registered for channel '{dispatch.channel}'."
        )