class CampaignService:
    async def create_blueprint(self, campaign_id: str, directives: dict) -> dict:
        return {"status": "created", "campaign_id": campaign_id}
