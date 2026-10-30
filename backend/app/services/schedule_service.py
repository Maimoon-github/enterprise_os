class ScheduleService:
    async def register_campaign_schedule(self, campaign_id: str, platform: str, run_at_utc: str) -> str:
        return f"sched_{platform}_{campaign_id}"
