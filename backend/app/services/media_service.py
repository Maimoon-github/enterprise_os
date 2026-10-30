import logging
from typing import Any

from app.tasks.media_tasks import generate_media_asset, process_video_transcode

logger = logging.getLogger("services.media")


class MediaService:
    """Manages synthetic image/video generation and transcoding via Celery media_queue."""

    async def process_media_generation(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        campaign_id: str = "default_campaign",
        platform: str = "linkedin",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch media generation task to media_queue."""
        task_res = generate_media_asset.apply_async(
            args=[prompt, aspect_ratio, campaign_id, platform, thread_id],
            queue="media_queue",
        )
        return {
            "status": "queued",
            "task_id": task_res.id,
            "campaign_id": campaign_id,
            "platform": platform,
            "aspect_ratio": aspect_ratio,
        }

    async def transcode_video(
        self,
        input_key: str,
        output_key: str,
        target_ratio: str = "9:16",
    ) -> dict[str, Any]:
        """Dispatch video transcoding task to media_queue."""
        task_res = process_video_transcode.apply_async(
            args=[input_key, output_key, target_ratio],
            queue="media_queue",
        )
        return {
            "status": "queued",
            "task_id": task_res.id,
            "output_key": output_key,
            "target_ratio": target_ratio,
        }
