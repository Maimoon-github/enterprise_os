"""Analytics FastMCP Server (Streamable HTTP / stdio transport)
Adheres to MCP 2026-07-28 specification.
Exposes PostgreSQL analytics aggregates and Polars rolling Z-score anomaly detection.
"""
from typing import Any

from fastmcp import FastMCP
from mcp_servers.analytics_server.tools import (
    execute_detect_anomalies,
    execute_export_campaign_report,
    execute_query_aggregated_kpis,
)

mcp = FastMCP("AnalyticsServer")


@mcp.resource("analytics://schema")
def get_analytics_schema() -> dict[str, Any]:
    """Exposes database schema and available dimensions for analytics events."""
    return {
        "table": "analytics_events",
        "dimensions": ["brand_id", "platform", "external_post_id", "metric_type"],
        "metrics": ["impressions", "clicks", "conversions", "reactions", "shares"],
    }


@mcp.resource("analytics://kpi_definitions")
def get_kpi_definitions() -> dict[str, str]:
    """Returns canonical definitions and mathematical formulations of cross-platform KPIs."""
    return {
        "CTR": "Clicks / Impressions",
        "Z_Score": "(Metric_t - Mean_28d) / Std_28d",
        "Breakout_Threshold": "Z > +1.5",
        "Underperformance_Threshold": "Z < -1.5",
    }


@mcp.tool()
def query_aggregated_kpis(
    start_date: str,
    end_date: str,
    platforms: list[str],
) -> dict[str, Any]:
    """Computes aggregated cross-platform metrics (impressions, clicks, average CTR, conversions)."""
    return execute_query_aggregated_kpis(start_date=start_date, end_date=end_date, platforms=platforms)


@mcp.tool()
def detect_metric_anomalies(
    lookback_days: int = 28,
    z_threshold: float = 1.5,
) -> list[dict[str, Any]]:
    """Runs Polars rolling 7d/28d Z-score anomaly detection identifying breakout or underperforming platforms."""
    return execute_detect_anomalies(lookback_days=lookback_days, z_threshold=z_threshold)


@mcp.tool()
def export_campaign_report(campaign_id: str) -> dict[str, Any]:
    """Generates an exportable PDF/CSV summary report for a campaign."""
    return execute_export_campaign_report(campaign_id=campaign_id)


if __name__ == "__main__":
    mcp.run(transport="sse", port=8084)
