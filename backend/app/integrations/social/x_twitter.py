from app.integrations.social.base_adapter import BaseSocialAdapter

class XTwitterAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "x", "status": "published", "tweet_id": "184920492019"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"impressions": 4200, "reposts": 14, "likes": 98}
