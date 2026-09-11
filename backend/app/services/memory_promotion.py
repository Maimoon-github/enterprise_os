"""Promotes validated learning deltas into institutional memory."""
from __future__ import annotations


class MemoryPromotionService:
    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def promote(self, tenant_id: str, delta: dict) -> bool:
        confidence = float(delta.get("confidence", 0.0))
        if confidence < self.threshold:
            return False
        # Persistence delegated to repository in production.
        return True
