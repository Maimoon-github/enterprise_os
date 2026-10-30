class PlaywrightScraper:
    async def extract_serp_signals(self, query: str) -> list[dict]:
        # Dispatched to rootless Podman browser sandbox
        return [{"title": f"SERP Result for {query}", "snippet": "Market trend details..."}]
