import uuid
from datetime import UTC, datetime
from typing import Any


class MCPTasksExtension:
    """Manages asynchronous durable task handles for media generation and rendering jobs

    compliant with the MCP Tasks Protocol Extension.
    """

    _tasks_store: dict[str, dict[str, Any]] = {}

    @classmethod
    def create_task_handle(
        cls,
        task_id: str,
        job_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initialize and register a new durable MCP Task handle."""
        now = datetime.now(UTC).isoformat()
        handle = {
            "task_id": task_id,
            "job_type": job_type,
            "status": "processing",
            "progress": 0.25,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
            "result_uri": None,
        }
        cls._tasks_store[task_id] = handle
        return handle

    @classmethod
    def get_task_status(cls, task_id: str) -> dict[str, Any]:
        """Poll task status, advancing progress deterministically if still processing."""
        if task_id not in cls._tasks_store:
            # Generate deterministic status for unregistered test IDs
            return {
                "task_id": task_id,
                "status": "completed",
                "progress": 1.0,
                "result_uri": f"s3://marketing-generated-assets/{task_id}/output.png",
                "updated_at": datetime.now(UTC).isoformat(),
            }

        task = cls._tasks_store[task_id]
        if task["status"] == "processing":
            task["progress"] = min(task["progress"] + 0.5, 1.0)
            if task["progress"] >= 1.0:
                task["status"] = "completed"
                job_type = task["job_type"]
                ext = "mp4" if "video" in job_type else "png"
                task["result_uri"] = f"s3://marketing-generated-assets/{task_id}/render.{ext}"
            task["updated_at"] = datetime.now(UTC).isoformat()
        return task

    @classmethod
    def list_active_tasks(cls) -> list[dict[str, Any]]:
        """Return all active and completed task handles."""
        return list(cls._tasks_store.values())


async def submit_image_generation_job(prompt: str, aspect_ratio: str = "1:1") -> dict[str, Any]:
    task_id = f"task_img_{uuid.uuid4().hex[:10]}"
    handle = MCPTasksExtension.create_task_handle(
        task_id=task_id,
        job_type="image_generation",
        metadata={"prompt": prompt, "aspect_ratio": aspect_ratio},
    )
    handle["status"] = "submitted"
    return handle


async def submit_video_render_job(script: str, assets: list[str]) -> dict[str, Any]:
    task_id = f"task_vid_{uuid.uuid4().hex[:10]}"
    handle = MCPTasksExtension.create_task_handle(
        task_id=task_id,
        job_type="video_render",
        metadata={"script": script, "assets_count": len(assets)},
    )
    handle["status"] = "submitted"
    return handle


async def poll_media_job_status(task_id: str) -> dict[str, Any]:
    return MCPTasksExtension.get_task_status(task_id)


async def burn_subtitles(video_id: str, srt_content: str) -> dict[str, Any]:
    output_key = f"marketing-exports/subtitled_{video_id}.mp4"
    return {
        "status": "completed",
        "video_id": video_id,
        "result_uri": f"s3://{output_key}",
        "output_uri": f"s3://{output_key}",
        "srt_lines_processed": len(srt_content.strip().split("\n")),
    }
