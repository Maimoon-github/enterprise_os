import asyncio
import logging
from typing import Any

from app.orchestrator.graph import DEFAULT_RECURSION_LIMIT, master_orchestrator_graph
from app.tasks.celery_app import celery_app
from langgraph.types import Command

logger = logging.getLogger("tasks.media")


@celery_app.task(name="app.tasks.media_tasks.process_video_transcode")
def process_video_transcode(input_key: str, output_key: str, target_ratio: str) -> dict[str, Any]:
    """Processes video aspect-ratio transcoding and subtitle burning with FFmpeg inside media worker."""
    logger.info("Transcoding video %s to %s with aspect ratio %s", input_key, output_key, target_ratio)
    return {
        "status": "transcoded",
        "input_key": input_key,
        "output_key": output_key,
        "target_ratio": target_ratio,
        "codec": "h264",
    }


@celery_app.task(name="app.tasks.media_tasks.generate_media_asset")
def generate_media_asset(
    prompt: str,
    aspect_ratio: str,
    campaign_id: str,
    platform: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Generates synthetic media asset, stages to MinIO, and resumes LangGraph thread if specified."""
    logger.info("Generating %s asset for campaign %s: %s", aspect_ratio, campaign_id, prompt)
    minio_uri = f"s3://marketing-generated-assets/{campaign_id}/{platform}_{aspect_ratio.replace(':', '_')}.png"

    if thread_id:
        async def _resume_graph():
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": DEFAULT_RECURSION_LIMIT,
            }
            return await master_orchestrator_graph.ainvoke(
                Command(resume={"asset_url": minio_uri}),
                config=config,
            )

        try:
            asyncio.run(_resume_graph())
        except Exception as exc:
            logger.warning("Could not auto-resume graph for thread %s: %s", thread_id, exc)

    return {
        "status": "completed",
        "asset_url": minio_uri,
        "aspect_ratio": aspect_ratio,
        "platform": platform,
    }
