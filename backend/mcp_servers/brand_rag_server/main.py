"""Brand RAG FastMCP Server (Streamable HTTP / stdio transport)
Adheres to MCP 2026-07-28 specification.
Exposes hybrid Qdrant + FastEmbed retrieval and brand voice guidelines.
"""
from typing import Any

from fastmcp import FastMCP
from mcp_servers.brand_rag_server.resources import (
    get_brand_voice_guidelines,
    get_persona_guidelines,
)
from mcp_servers.brand_rag_server.tools import (
    retrieve_winning_campaigns as _retrieve_winning_campaigns,
)
from mcp_servers.brand_rag_server.tools import (
    search_brand_knowledge as _search_brand_knowledge,
)
from mcp_servers.brand_rag_server.tools import (
    store_campaign_learnings as _store_campaign_learnings,
)

mcp = FastMCP("BrandRAGServer")


@mcp.resource("brand://guidelines/{brand_id}")
def get_brand_guidelines_resource(brand_id: str) -> str:
    """Retrieves authoritative brand voice, pillars, and prohibited vocabulary."""
    return get_brand_voice_guidelines(brand_id)


@mcp.resource("brand://personas/{segment_id}")
def get_persona_resource(segment_id: str) -> str:
    """Retrieves audience segment positioning, pain points, and conversion hooks."""
    return get_persona_guidelines(segment_id)


@mcp.tool()
def search_brand_knowledge(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Hybrid dense vector + FastEmbed sparse search across Qdrant brand collections with cross-encoder reranking."""
    return _search_brand_knowledge(query=query, limit=limit)


@mcp.tool()
def retrieve_winning_campaigns(objective: str, platform: str | None = None) -> list[dict[str, Any]]:
    """Retrieves historically winning campaign blueprints matching the objective and platform."""
    return _retrieve_winning_campaigns(objective=objective, platform=platform)


@mcp.tool()
def store_campaign_learnings(campaign_id: str, learnings: dict[str, Any]) -> dict[str, Any]:
    """Stores post-execution learnings back into the market intelligence knowledge base."""
    return _store_campaign_learnings(campaign_id=campaign_id, learnings=learnings)


if __name__ == "__main__":
    mcp.run(transport="sse", port=8081)
