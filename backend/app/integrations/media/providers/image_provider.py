class ImageGenerationProvider:
    async def generate_image(self, prompt: str, aspect_ratio: str) -> dict:
        return {"status": "success", "image_url": "s3://marketing-generated-assets/demo_img.png"}
