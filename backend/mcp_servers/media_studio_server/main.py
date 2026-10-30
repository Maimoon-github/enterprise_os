"""Media Studio FastMCP Server (Streamable HTTP / stdio transport + Tasks Extension)
Adheres to MCP 2026-07-28 specification.
Handles MinIO object storage bindings and durable asynchronous media generation handles.
"""
from typing import Any

from fastmcp import FastMCP
from mcp_servers.media_studio_server.tasks_extension import (
    burn_subtitles as _burn_subtitles,
)
from mcp_servers.media_studio_server.tasks_extension import (
    poll_media_job_status as _poll_media_job_status,
)
from mcp_servers.media_studio_server.tasks_extension import (
    submit_image_generation_job as _submit_image_generation_job,
)
from mcp_servers.media_studio_server.tasks_extension import (
    submit_video_render_job as _submit_video_render_job,
)

mcp = FastMCP("MediaStudioServer")


@mcp.resource("media://asset_catalog/{campaign_id}")
def get_campaign_assets(campaign_id: str) -> list[dict[str, Any]]:
    """Retrieves MinIO asset metadata, aspect ratios, and SHA-256 content hashes for a campaign."""
    return [
        {
            "campaign_id": campaign_id,
            "asset_id": f"asset_{campaign_id}_1x1",
            "bucket": "marketing-generated-assets",
            "key": f"{campaign_id}/linkedin_square.png",
            "aspect_ratio": "1:1",
            "content_hash": "sha256_8f92a104c8e762dfb312",
            "uri": f"s3://marketing-generated-assets/{campaign_id}/linkedin_square.png",
        },
        {
            "campaign_id": campaign_id,
            "asset_id": f"asset_{campaign_id}_9x16",
            "bucket": "marketing-generated-assets",
            "key": f"{campaign_id}/reels_vertical.mp4",
            "aspect_ratio": "9:16",
            "content_hash": "sha256_3b1297cc89fa7120a402",
            "uri": f"s3://marketing-generated-assets/{campaign_id}/reels_vertical.mp4",
        },
    ]


@mcp.tool()
async def submit_image_generation_job(prompt: str, aspect_ratio: str = "1:1") -> dict[str, Any]:
    """Submits an asynchronous synthetic image generation job returning a durable MCP Task handle."""
    return await _submit_image_generation_job(prompt, aspect_ratio)


@mcp.tool()
async def submit_video_render_job(script: str, assets: list[str]) -> dict[str, Any]:
    """Submits an asynchronous video composition job with subtitle burning via FFmpeg."""
    return await _submit_video_render_job(script, assets)


@mcp.tool()
async def poll_media_job_status(task_id: str) -> dict[str, Any]:
    """Polls progress and result URI for a durable MCP Task handle."""
    return await _poll_media_job_status(task_id)


@mcp.tool()
async def burn_subtitles(video_id: str, srt_content: str) -> dict[str, Any]:
    """Burns subtitles into video asset with FFmpeg transcoding to 9:16 / 16:9 outputs."""
    return await _burn_subtitles(video_id, srt_content)


if __name__ == "__main__":
    mcp.run(transport="sse", port=8083)
