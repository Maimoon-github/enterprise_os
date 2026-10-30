from app.integrations.social.base_adapter import BaseSocialAdapter

class InstagramAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "instagram", "status": "published", "post_id": "ig_media_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"reach": 2100, "impressions": 2800, "saves": 40}
