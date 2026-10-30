from app.integrations.social.base_adapter import BaseSocialAdapter


class YouTubeAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "youtube", "status": "published", "video_id": "yt_video_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"views": 3400, "likes": 180, "watch_time_minutes": 520}
