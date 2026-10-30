from app.integrations.social.base_adapter import BaseSocialAdapter


class FacebookAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "facebook", "status": "published", "post_id": "fb_post_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"reach": 1800, "clicks": 28, "shares": 5}
