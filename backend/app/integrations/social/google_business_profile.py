from app.integrations.social.base_adapter import BaseSocialAdapter


class GoogleBusinessProfileAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "google_business_profile", "status": "published", "post_id": "gbp_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"views": 620, "actions": 34}
