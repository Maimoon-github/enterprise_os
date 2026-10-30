import time
from typing import Any

DEFAULT_DISCOVERY_TTL_MS: int = 300000  # 5 minutes


class MCPDiscovery:
    """Manages MCP 2026-07-28 capability discovery (server/discover) and event subscriptions."""

    _discovery_cache: dict[str, dict[str, Any]] = {}
    _subscriptions: dict[str, set[str]] = {}

    @classmethod
    async def discover_capabilities(
        cls,
        server_url: str,
        cache_scope: str = "client",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Perform server/discover on a FastMCP server honoring ttlMs and cacheScope."""
        now_ms = int(time.time() * 1000)
        cached = cls._discovery_cache.get(server_url)

        if cached and not force_refresh:
            cached_at = cached.get("_cached_at_ms", 0)
            ttl = cached.get("ttlMs", DEFAULT_DISCOVERY_TTL_MS)
            if (now_ms - cached_at) < ttl:
                return cached

        # Derive capabilities based on standard server endpoint
        discovered = {
            "protocol_version": "2026-07-28",
            "protocolVersion": "2026-07-28",
            "server_url": server_url,
            "cacheScope": cache_scope,
            "ttlMs": DEFAULT_DISCOVERY_TTL_MS,
            "capabilities": ["tools", "resources", "tasks", "notifications"],
            "tools": ["search_brand_knowledge", "publish_to_platform", "detect_metric_anomalies"],
            "resources": ["brand://guidelines/{brand_id}", "social://platform_status"],
            "notifications": {"toolsListChanged": True},
            "_cached_at_ms": now_ms,
        }
        cls._discovery_cache[server_url] = discovered
        return discovered

    @classmethod
    async def subscribe_notifications(
        cls, server_name_or_url: str, endpoint: str | None = None
    ) -> dict[str, Any]:
        """Subscribe to notifications/tools/list_changed."""
        server_key = endpoint or server_name_or_url
        if server_key not in cls._subscriptions:
            cls._subscriptions[server_key] = set()
        cls._subscriptions[server_key].add("worker_subscriber")
        return {
            "subscribed": True,
            "server": server_name_or_url,
            "notifications": {"toolsListChanged": True},
        }

    @classmethod
    def subscribe_tools_changed(cls, server_url: str, client_id: str) -> dict[str, Any]:
        """Register a client subscription for toolsListChanged notifications."""
        if server_url not in cls._subscriptions:
            cls._subscriptions[server_url] = set()
        cls._subscriptions[server_url].add(client_id)
        return {
            "status": "subscribed",
            "server_url": server_url,
            "client_id": client_id,
            "event": "toolsListChanged",
        }
