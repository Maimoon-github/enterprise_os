from typing import Any


class ToolsetRegistry:
    """Central registry mapping agents and tasks to scoped FastMCP toolsets."""

    def __init__(self):
        self._toolsets: dict[str, list[dict[str, Any]]] = {
            "research_strategy": [
                {"name": "search_brand_knowledge", "server": "brand_rag_server", "mutating": False},
                {"name": "retrieve_winning_campaigns", "server": "brand_rag_server", "mutating": False},
            ],
            "campaign_creative": [
                {"name": "search_brand_knowledge", "server": "brand_rag_server", "mutating": False},
                {"name": "submit_image_generation_job", "server": "media_studio_server", "mutating": True},
            ],
            "publishing_fanout": [
                {"name": "publish_to_platform", "server": "social_gateway_server", "mutating": True},
                {"name": "verify_platform_post", "server": "social_gateway_server", "mutating": False},
            ],
            "closed_loop_eval": [
                {"name": "query_aggregated_kpis", "server": "analytics_server", "mutating": False},
                {"name": "detect_metric_anomalies", "server": "analytics_server", "mutating": False},
            ],
        }

    def register_toolset(self, name: str, tools: list[dict[str, Any]]) -> None:
        self._toolsets[name] = tools

    def get_toolset(self, name: str) -> list[dict[str, Any]]:
        return self._toolsets.get(name, [])

    def list_all_toolsets(self) -> dict[str, list[dict[str, Any]]]:
        return self._toolsets


toolset_registry = ToolsetRegistry()
