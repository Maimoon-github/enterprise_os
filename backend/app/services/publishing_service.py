class PublishingService:
    async def fanout_publish(self, campaign_id: str, platform_payloads: list[dict]) -> list[dict]:
        return [{"status": "success", "idempotency_key": p.get("idempotency_key")} for p in platform_payloads]
