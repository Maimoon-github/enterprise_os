"""Normalizes and persists omnichannel performance events."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType


class TelemetryNormalizer:
    """Normalizes raw webhook/pixel/event payloads into ``TelemetryEvent`` records."""

    def __init__(self, repository: TelemetryRepository) -> None:
        self._repository = repository

    def normalize(
        self,
        *,
        tenant_id: str,
        event_type: TelemetryEventType,
        channel: str,
        occurred_at: datetime,
        metrics: dict[str, float],
    ) -> TelemetryEvent:
        """Build a normalized ``TelemetryEvent`` from raw fields."""

        return TelemetryEvent(
            event_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            channel=channel,
            occurred_at=occurred_at,
            metrics=metrics,
        )

    async def ingest(
        self,
        *,
        tenant_id: str,
        event_type: TelemetryEventType,
        channel: str,
        occurred_at: datetime,
        metrics: dict[str, float],
    ) -> TelemetryEvent:
        """Normalize and persist a raw telemetry payload, returning the stored event."""

        event = self.normalize(
            tenant_id=tenant_id,
            event_type=event_type,
            channel=channel,
            occurred_at=occurred_at,
            metrics=metrics,
        )
        await self._repository.record(event)
        return event

    async def for_learning_loop(self, tenant_id: str) -> list[TelemetryEvent]:
        """Return ROAS events feeding W_LEARN's attribution and decay analysis."""

        return await self._repository.list_by_type(tenant_id, TelemetryEventType.ROAS.value)