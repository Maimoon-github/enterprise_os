"""Promotes validated learning deltas into institutional memory."""

from __future__ import annotations

import uuid

from app.persistence.repositories.memory import MemoryRecord, MemoryRepository

_MIN_PROMOTION_CONFIDENCE = 0.7


class MemoryPromotionService:
    """Promotes a validated learning delta once it clears a confidence bar."""

    def __init__(
        self, repository: MemoryRepository, *, min_confidence: float = _MIN_PROMOTION_CONFIDENCE
    ) -> None:
        self._repository = repository
        self._min_confidence = min_confidence

    async def promote(
        self,
        *,
        tenant_id: str,
        category: str,
        statement: str,
        confidence: float,
        source_task_ids: list[str],
    ) -> MemoryRecord | None:
        """Promote and persist a learning delta, or return None if not validated."""

        if confidence < self._min_confidence:
            return None

        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            category=category,
            statement=statement,
            confidence=confidence,
            source_task_ids=source_task_ids,
        )
        await self._repository.promote(record)
        return record