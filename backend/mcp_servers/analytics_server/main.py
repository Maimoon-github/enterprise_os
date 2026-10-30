"""Analytics FastMCP Server (Streamable HTTP transport)
Exposes aggregated cross-platform metrics and anomaly detection tools.
"""
from fastmcp import FastMCP

mcp = FastMCP("AnalyticsServer")

@mcp.tool()
def query_aggregated_kpis(start_date: str, end_date: str, platforms: list[str]) -> dict:
    return {
        "platforms": platforms,
        "total_impressions": 50000,
        "total_clicks": 1800,
        "average_ctr": 0.036,
    }

if __name__ == "__main__":
    mcp.run(transport="sse", port=8084)
