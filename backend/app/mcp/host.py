from typing import Any

from app.mcp.client import MCPClient
from app.mcp.discovery import MCPDiscovery


class MCPHost:
    """Manages connections, discovery caching, and routing to registered FastMCP servers."""

    def __init__(self):
        self._servers: dict[str, dict[str, Any]] = {
            "brand_rag_server": {
                "name": "brand_rag_server",
                "endpoint": "http://localhost:8081",
                "transport": "Streamable HTTP",
                "capabilities": ["tools", "resources"],
                "tools": ["search_brand_knowledge", "retrieve_winning_campaigns", "store_campaign_learnings"],
                "resources": ["brand://guidelines/{brand_id}", "brand://personas/{segment_id}"],
            },
            "social_gateway_server": {
                "name": "social_gateway_server",
                "endpoint": "http://localhost:8082",
                "transport": "Streamable HTTP",
                "capabilities": ["tools", "resources", "notifications"],
                "tools": ["publish_to_platform", "verify_platform_post", "fetch_platform_metrics"],
                "resources": ["social://platform_status", "social://rate_limits"],
            },
            "media_studio_server": {
                "name": "media_studio_server",
                "endpoint": "http://localhost:8083",
                "transport": "Streamable HTTP",
                "capabilities": ["tools", "resources", "tasks"],
                "tools": ["submit_image_generation_job", "submit_video_render_job", "poll_media_job_status", "burn_subtitles"],
                "resources": ["media://asset_catalog/{campaign_id}"],
            },
            "analytics_server": {
                "name": "analytics_server",
                "endpoint": "http://localhost:8084",
                "transport": "Streamable HTTP",
                "capabilities": ["tools", "resources"],
                "tools": ["query_aggregated_kpis", "detect_metric_anomalies", "export_campaign_report"],
                "resources": ["analytics://schema", "analytics://kpi_definitions"],
            },
        }

    def register_server(self, name: str, endpoint: str, capabilities: list[str] | None = None) -> None:
        self._servers[name] = {
            "name": name,
            "endpoint": endpoint,
            "transport": "Streamable HTTP",
            "capabilities": capabilities or ["tools", "resources"],
            "tools": [],
            "resources": [],
        }

    def get_server(self, name: str) -> dict[str, Any] | None:
        return self._servers.get(name)

    def list_servers(self) -> list[dict[str, Any]]:
        return list(self._servers.values())

    def get_client(self, server_name: str) -> MCPClient:
        server = self.get_server(server_name)
        endpoint = server["endpoint"] if server else "http://localhost:8080"
        return MCPClient(endpoint)

    async def sync_server(self, server_name: str) -> dict[str, Any]:
        """Trigger server/discover and update local tool/resource inventory."""
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Unknown MCP server: {server_name}")
        discovery = await MCPDiscovery.discover_capabilities(server["endpoint"], force_refresh=True)
        return {
            "server_id": server_name,
            "status": "synced",
            "tools_synced": len(server.get("tools", [])),
            "resources_synced": len(server.get("resources", [])),
            "discovery": discovery,
        }


mcp_host = MCPHost()
