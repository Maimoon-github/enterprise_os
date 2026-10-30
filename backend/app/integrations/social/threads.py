from app.integrations.social.base_adapter import BaseSocialAdapter

class ThreadsAdapter(BaseSocialAdapter):
    async def publish(self, payload: dict, credentials: dict) -> dict:
        return {"platform": "threads", "status": "published", "post_id": "th_post_12345"}

    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        return {"views": 1500, "replies": 12, "likes": 65}
