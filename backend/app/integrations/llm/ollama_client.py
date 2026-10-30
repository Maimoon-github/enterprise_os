import httpx
from app.core.config import settings


class OllamaClient:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL):
        self.base_url = base_url

    async def generate(self, model: str, prompt: str, system: str | None = None) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120.0) as client:
            payload = {"model": model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "")

ollama_client = OllamaClient()
