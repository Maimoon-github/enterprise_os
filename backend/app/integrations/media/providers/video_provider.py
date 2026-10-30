class VideoGenerationProvider:
    async def generate_video(self, prompt: str, duration_sec: int) -> dict:
        return {"status": "queued", "task_id": "vid_task_12345"}
