from app.integrations.social.base_adapter import BaseSocialAdapter

class LinkedInAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "linkedin", "status": "published", "post_id": "urn:li:share:12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"impressions": 1200, "clicks": 45, "reactions": 32}
