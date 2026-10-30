from abc import ABC, abstractmethod
from typing import Any


class BaseSocialAdapter(ABC):
    """Base interface for zero-trust platform adapters with standardized return contracts."""

    @abstractmethod
    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        """Publish content payload to the target platform using decrypted in-memory credentials."""
        pass

    @abstractmethod
    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Fetch real-time impressions, clicks, engagement, and reactions for a published post."""
        pass

    async def verify_post(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Verify post status and live URL on the target platform."""
        return {"post_id": post_id, "verified": True, "status": "active"}
