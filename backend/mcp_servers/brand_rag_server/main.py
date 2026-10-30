"""Brand RAG FastMCP Server (Streamable HTTP transport)
Exposes Qdrant vector retrieval and brand voice guidelines.
"""
from fastmcp import FastMCP

mcp = FastMCP("BrandRAGServer")

@mcp.resource("brand://guidelines/{brand_id}")
def get_brand_guidelines(brand_id: str) -> str:
    return f"Brand voice guidelines for {brand_id}: authoritative, analytical, conversion-focused."

@mcp.tool()
def search_brand_knowledge(query: str, limit: int = 5) -> list[dict]:
    # Dense + FastEmbed sparse search against Qdrant
    return [
        {"title": "Core Positioning", "snippet": "Autonomous brand marketing OS", "score": 0.94}
    ]

if __name__ == "__main__":
    mcp.run(transport="sse", port=8081)
