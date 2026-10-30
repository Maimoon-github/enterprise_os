"""Media Studio FastMCP Server (Streamable HTTP + Tasks Extension)
Handles MinIO asset storage and asynchronous media generation handles.
"""
import uuid

from fastmcp import FastMCP

mcp = FastMCP("MediaStudioServer")

@mcp.resource("media://asset_catalog/{campaign_id}")
def get_campaign_assets(campaign_id: str) -> list[dict]:
    return []

@mcp.tool()
def submit_image_generation_job(prompt: str, aspect_ratio: str) -> dict:
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    return {
        "task_id": task_id,
        "status": "queued",
        "aspect_ratio": aspect_ratio,
    }

if __name__ == "__main__":
    mcp.run(transport="sse", port=8083)
