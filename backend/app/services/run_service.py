class RunService:
    async def dispatch_orchestrator(self, campaign_id: str) -> str:
        return "thread_new_run"
