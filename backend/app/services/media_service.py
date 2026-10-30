class MediaService:
    async def process_media_generation(self, prompt: str, aspect_ratio: str) -> dict:
        return {"status": "completed", "asset_key": "marketing-generated-assets/final.png"}
