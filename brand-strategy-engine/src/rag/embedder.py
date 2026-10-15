"""Asynchronous Ollama embedding client for nomic-embed-text (768-dim)."""

import hashlib
import logging
import math
import os
from typing import List
import httpx

logger = logging.getLogger(__name__)


class OllamaEmbedder:
    """Client for generating 768-dimensional dense vector embeddings via local Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text:latest",
        dimension: int = 768,
        timeout: float = 30.0,
    ):
        self.base_url = os.getenv("OLLAMA_BASE_URL", base_url).rstrip("/")
        # If /v1 is appended, strip it for Ollama native endpoints
        if self.base_url.endswith("/v1"):
            self.api_url = f"{self.base_url[:-3]}/api/embeddings"
        else:
            self.api_url = f"{self.base_url}/api/embeddings"
        self.model = model
        self.dimension = dimension
        self.timeout = timeout

    def _fallback_embedding(self, text: str) -> List[float]:
        """Deterministic 768-dimensional token-projected embedding fallback when Ollama is offline."""
        import re
        vec = [0.0] * self.dimension
        stopwords = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by",
            "of", "from", "is", "are", "was", "were", "be", "been", "our", "your",
            "their", "its", "per", "that", "this", "it"
        }
        raw_words = re.findall(r"\w+", text.lower())
        words = []
        for w in raw_words:
            if w in stopwords:
                continue
            if len(w) > 4 and w.endswith("ing"):
                w = w[:-3]
            elif len(w) > 4 and w.endswith("ed"):
                w = w[:-2]
            elif len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
                w = w[:-1]
            words.append(w)

        if not words:
            words = [text.lower().strip()] if text.strip() else ["empty"]

        for word in words:
            # Hash each token to deterministic dimensions
            h_int = int(hashlib.sha256(word.encode("utf-8")).hexdigest()[:16], 16)
            for d in range(4):
                idx = (h_int + (d * 193)) % self.dimension
                vec[idx] += 1.0

        # Normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    async def embed_text(self, text: str) -> List[float]:
        """Generates 768-dim dense embedding for a single text string."""
        if not text.strip():
            return [0.0] * self.dimension

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {"model": self.model, "prompt": text}
                resp = await client.post(self.api_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    embedding = data.get("embedding", [])
                    if len(embedding) == self.dimension:
                        norm = math.sqrt(sum(x * x for x in embedding)) or 1.0
                        return [round(x / norm, 6) for x in embedding]
        except Exception as e:
            logger.debug("Ollama embedding endpoint unavailable (%s), using local fallback", e)

        return self._fallback_embedding(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of strings."""
        return [await self.embed_text(t) for t in texts]
