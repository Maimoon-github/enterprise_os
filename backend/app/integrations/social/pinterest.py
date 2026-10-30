from app.integrations.social.base_adapter import BaseSocialAdapter


class PinterestAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "pinterest", "status": "published", "pin_id": "pin_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"saves": 22, "impressions": 850, "clicks": 18}
